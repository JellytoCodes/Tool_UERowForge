"""Bounded, read-only OOXML reader. No Excel installation or third-party packages.

Only .xlsx, plain cell values, shared/inline strings, numbers and booleans are
supported. Formulas and Excel errors are surfaced, never evaluated or silently
replaced by possibly stale cached values. Dates are marked for rejection by the
schema validator. This is intentionally not a general-purpose Excel engine.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
import posixpath
import re
from zipfile import ZipFile, BadZipFile
from xml.etree import ElementTree as ET

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
RID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
MAX_ARCHIVE = 32 * 1024 * 1024
MAX_EXPANDED = 96 * 1024 * 1024
MAX_MEMBER = 32 * 1024 * 1024
MAX_CELLS = 250_000
MAX_ROWS = 50_003
MAX_COLS = 128


class WorkbookError(ValueError):
    pass


@dataclass(frozen=True)
class SpecialCell:
    kind: str
    text: str


@dataclass
class Sheet:
    name: str
    cells: dict[tuple[int, int], object] = field(default_factory=dict)
    merged: list[str] = field(default_factory=list)

    def get(self, row: int, col: int) -> object:
        return self.cells.get((row, col))


def _xml(data: bytes) -> ET.Element:
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise WorkbookError("DTD/ENTITY가 포함된 XML은 지원하지 않습니다.")
    try:
        return ET.fromstring(data)
    except ET.ParseError as exc:
        raise WorkbookError(f"손상된 XLSX XML: {exc}") from exc


def _text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    parts = []
    for child in element:
        if child.tag == "{" + NS["m"] + "}t":
            parts.append(child.text or "")
        elif child.tag == "{" + NS["m"] + "}r":
            parts.extend(n.text or "" for n in child.findall("m:t", NS))
        # rPh is a phonetic guide, not part of the stored string value.
    text = "".join(parts)
    text = re.sub(r"_x([0-9a-fA-F]{4})_", lambda m: chr(int(m[1], 16)), text)
    try:
        return text.encode("utf-16-le", "surrogatepass").decode("utf-16-le")
    except UnicodeError as exc:
        raise WorkbookError("XLSX 문자열에 잘못된 Unicode surrogate가 있습니다.") from exc


def _coordinate(value: str) -> tuple[int, int]:
    match = re.fullmatch(r"([A-Z]{1,3})([1-9][0-9]{0,6})", value)
    if not match:
        raise WorkbookError(f"잘못된 셀 주소: {value}")
    col = 0
    for c in match[1]:
        col = col * 26 + ord(c) - 64
    return int(match[2]), col


def _date_styles(z: ZipFile) -> set[int]:
    if "xl/styles.xml" not in z.namelist():
        return set()
    root = _xml(z.read("xl/styles.xml"))
    date_ids = set(range(14, 23)) | set(range(27, 37)) | set(range(45, 48)) | set(range(50, 59))
    for item in root.findall("m:numFmts/m:numFmt", NS):
        fmt = item.get("formatCode", "").lower()
        fmt = re.sub(r'"[^\"]*"|\\.|\[[^\]]*\]', "", fmt)
        if re.search(r"[ymdhis]", fmt):
            date_ids.add(int(item.get("numFmtId", "0")))
    return {
        index for index, xf in enumerate(root.findall("m:cellXfs/m:xf", NS))
        if int(xf.get("numFmtId", "0")) in date_ids
    }


def read_xlsx(path: Path) -> list[Sheet]:
    path = Path(path)
    if path.suffix.lower() != ".xlsx":
        raise WorkbookError(".xlsx만 지원합니다. .xls/.xlsm/CSV는 .xlsx로 저장해 주세요.")
    if path.stat().st_size > MAX_ARCHIVE:
        raise WorkbookError("파일이 너무 큽니다. 압축 파일 크기 제한: 32 MiB")
    try:
        with ZipFile(path) as z:
            entries = z.infolist()
            if len(entries) > 2048 or sum(i.file_size for i in entries) > MAX_EXPANDED:
                raise WorkbookError("XLSX 압축 해제 크기/파일 개수 제한을 초과했습니다.")
            if len({i.filename for i in entries}) != len(entries):
                raise WorkbookError("중복 ZIP 항목이 있는 XLSX는 지원하지 않습니다.")
            for info in entries:
                if info.file_size > MAX_MEMBER or info.flag_bits & 1:
                    raise WorkbookError("과대 XML 또는 암호화 XLSX는 지원하지 않습니다.")
            workbook = _xml(z.read("xl/workbook.xml"))
            rels = _xml(z.read("xl/_rels/workbook.xml.rels"))
            targets: dict[str, str] = {}
            for rel in rels:
                if rel.get("TargetMode") == "External":
                    continue
                target = rel.get("Target", "")
                normalized = posixpath.normpath(target.lstrip("/") if target.startswith("/") else "xl/" + target)
                if not normalized.startswith("xl/") or "\\" in normalized:
                    raise WorkbookError("허용되지 않는 XLSX 내부 경로입니다.")
                targets[rel.get("Id", "")] = normalized
            strings: list[str] = []
            if "xl/sharedStrings.xml" in z.namelist():
                strings = [_text(si) for si in _xml(z.read("xl/sharedStrings.xml")).findall("m:si", NS)]
            date_styles = _date_styles(z)
            results: list[Sheet] = []
            total_cells = 0
            for index, descriptor in enumerate(workbook.findall("m:sheets/m:sheet", NS)):
                name = descriptor.get("name", "")
                # The physical first sheet is always the workbook's guide.
                if index == 0 or name.startswith("_"):
                    continue
                target = targets.get(descriptor.get(RID, ""))
                if not target:
                    raise WorkbookError(f"[{name}] 워크시트 경로를 찾을 수 없습니다.")
                xml = _xml(z.read(target))
                if not xml.tag.endswith("}worksheet"):
                    continue
                sheet = Sheet(name)
                sheet.merged = [m.get("ref", "") for m in xml.findall("m:mergeCells/m:mergeCell", NS)]
                for cell in xml.findall("m:sheetData/m:row/m:c", NS):
                    value = cell.find("m:v", NS)
                    text = value.text if value is not None and value.text is not None else ""
                    formula = cell.find("m:f", NS)
                    inline = cell.find("m:is", NS)
                    if not text and formula is None and inline is None:
                        continue  # Ignore formatting-only cells.
                    total_cells += 1
                    if total_cells > MAX_CELLS:
                        raise WorkbookError("통합문서의 비어 있지 않은 셀이 250,000개를 초과합니다.")
                    row, col = _coordinate(cell.get("r", ""))
                    if row > MAX_ROWS or col > MAX_COLS:
                        raise WorkbookError(f"[{name}] 지원 범위 초과: 최대 50,000 데이터 행, 128열")
                    typ = cell.get("t", "n")
                    if formula is not None:
                        parsed: object = SpecialCell("수식", formula.text or "공유/배열 수식")
                    elif typ == "e":
                        parsed = SpecialCell("Excel 오류", text)
                    elif typ == "d" or int(cell.get("s", "0")) in date_styles and typ == "n":
                        parsed = SpecialCell("날짜/시간", text)
                    elif typ == "s":
                        try:
                            index = int(text)
                            if index < 0:
                                raise IndexError
                            parsed = strings[index]
                        except (ValueError, IndexError) as exc:
                            raise WorkbookError(f"[{name}] 손상된 shared string") from exc
                    elif typ == "inlineStr":
                        parsed = _text(inline)
                    elif typ == "b":
                        if text not in ("0", "1"):
                            raise WorkbookError(f"[{name}] 잘못된 bool 셀")
                        parsed = text == "1"
                    elif typ == "n":
                        try:
                            number = Decimal(text)
                            if not number.is_finite():
                                raise InvalidOperation
                            parsed = int(number) if number == number.to_integral_value() else float(number)
                        except (InvalidOperation, ValueError, OverflowError) as exc:
                            raise WorkbookError(f"[{name}] 잘못된 숫자: {text}") from exc
                    else:
                        parsed = text
                    if (row, col) in sheet.cells:
                        raise WorkbookError(f"[{name}] 중복 셀 주소")
                    sheet.cells[row, col] = parsed
                results.append(sheet)
            return results
    except (BadZipFile, KeyError, ET.ParseError) as exc:
        raise WorkbookError(f"올바른 .xlsx 파일이 아닙니다: {exc}") from exc
