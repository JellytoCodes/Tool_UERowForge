"""Project registration, strict table validation and guarded code generation."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import difflib
import hashlib
import json
import math
import os
from pathlib import Path, PureWindowsPath
import re
import tempfile
import uuid

from .xlsx_reader import Sheet, SpecialCell, read_xlsx
from .subsystem_codegen import SUBSYSTEM_MARKER, subsystem_header, subsystem_source

APP_ID = "UERowForge"
# Persistent file/INI identifiers stay unchanged to keep existing projects usable.
MARKER = "// UE TABLEDESK - MANAGED HEADER v1"
MANIFEST = ".tabledesk-manifest.json"
DEFAULT_HEADER_SUBDIR = "Data"
DEFAULT_JSON_SUBDIR = "DataTable"
GENERATOR_REVISION = 3
TYPES = {"string": "String", "fstring": "String", "name": "Name", "fname": "Name",
         "int": "Int", "int32": "Int", "float": "Float", "bool": "Bool", "rowkey": "RowKey"}
CPP = {"String": ("FString", 'TEXT("")'), "Name": ("FName", "NAME_None"),
       "Int": ("int32", "0"), "Float": ("float", "0.0f"), "Bool": ("bool", "false")}
RESERVED = set(("alignas alignof and and_eq asm atomic_cancel atomic_commit atomic_noexcept auto "
    "bitand bitor bool break case catch char char8_t char16_t char32_t class compl concept const "
    "consteval constexpr constinit const_cast continue co_await co_return co_yield decltype default "
    "delete do double dynamic_cast else enum explicit export extern false float for friend goto if "
    "inline int long mutable namespace new noexcept not not_eq nullptr operator or or_eq private "
    "protected public reflexpr register reinterpret_cast requires return short signed sizeof static "
    "static_assert static_cast struct switch synchronized template this thread_local throw true try "
    "typedef typeid typename union unsigned using virtual void volatile wchar_t while xor xor_eq "
    "StaticStruct GENERATED_BODY USTRUCT UPROPERTY Super OnPostDataImport OnDataTableChanged "
    "IsDataValid").casefold().split())
WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL"} | {f"{p}{i}" for p in ("COM", "LPT") for i in range(1, 10)}


class ToolError(ValueError):
    pass


def digest(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def json_text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def app_dir() -> Path:
    override = os.environ.get("UEROWFORGE_HOME") or os.environ.get("TABLEDESK_HOME")
    if override:
        return Path(override).expanduser().resolve()
    root = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local" / "share"))
    return root / APP_ID


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".td-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def relative_dir(raw: str, *, unreal: bool = False) -> str:
    raw = raw.strip()
    if not raw:
        return ""
    if PureWindowsPath(raw).drive or raw.startswith(("/", "\\")):
        raise ToolError("절대 경로는 지정할 수 없습니다. 하위 상대 경로만 입력하세요.")
    parts = raw.replace("\\", "/").split("/")
    for part in parts:
        if not part or part in (".", "..") or part != part.rstrip(" ."):
            raise ToolError("빈 경로, '.' 또는 '..', 끝의 공백/마침표는 허용하지 않습니다.")
        if re.search(r'[<>:"|?*\x00-\x1f]', part) or part.split(".")[0].upper() in WINDOWS_RESERVED:
            raise ToolError(f"사용할 수 없는 경로 구성요소: {part}")
        if unreal and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", part):
            raise ToolError("에셋/헤더 하위 경로는 영문, 숫자, 밑줄만 사용하세요.")
    return "/".join(parts)


def inside(root: Path, relative: str) -> Path:
    rel = relative_dir(relative)
    root = root.resolve()
    dest = (root / rel).resolve()
    if not dest.is_relative_to(root):
        raise ToolError(f"프로젝트 밖을 가리키는 링크/경로를 차단했습니다: {relative}")
    return dest


def scoped(project_root: Path, base: str, child: str) -> Path:
    """Check both project containment and the narrower configured output base."""
    anchor = inside(project_root, base)
    target = inside(project_root, "/".join(x for x in (base, child) if x))
    if not target.is_relative_to(anchor):
        raise ToolError("허용된 출력 폴더 밖으로 나가는 경로입니다.")
    return target


def identifier(value: str, label: str) -> str:
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", value):
        raise ToolError(f"{label}: 영문으로 시작하는 영문/숫자/밑줄 1~64자로 입력하세요: {value!r}")
    if value.casefold() in RESERVED:
        raise ToolError(f"{label}: C++ 또는 엔진 예약 이름입니다: {value}")
    return value


@dataclass
class Project:
    id: str
    uproject: str
    name: str
    module: str
    prefix: str = ""
    header_subdir: str = DEFAULT_HEADER_SUBDIR
    json_subdir: str = DEFAULT_JSON_SUBDIR
    asset_subdir: str = "DataTables"
    sources: list[str] = field(default_factory=list)
    routes: dict[str, str] = field(default_factory=dict)
    engine_cmd: str = ""
    last_conversion: str = ""

    @property
    def root(self) -> Path:
        return Path(self.uproject).parent.resolve()

    @property
    def header_name(self) -> str:
        return f"{self.prefix}StructTypes.h"

    @property
    def header_relative(self) -> str:
        return "/".join(x for x in ("Source", self.module, "Public", self.header_subdir, self.header_name) if x)

    @property
    def subsystem_header_relative(self) -> str:
        return "/".join(x for x in ("Source", self.module, "Public", self.header_subdir, "DataTableSubsystem.h") if x)

    @property
    def subsystem_source_relative(self) -> str:
        return "/".join(x for x in ("Source", self.module, "Private", self.header_subdir, "DataTableSubsystem.cpp") if x)

    def check(self) -> None:
        if not Path(self.uproject).is_file():
            raise ToolError("등록된 .uproject를 찾을 수 없습니다. 프로젝트를 다시 등록하세요.")
        identifier(self.module, "모듈명")
        if self.prefix:
            identifier(self.prefix, "접두사")
        if len(self.prefix) > 24:
            raise ToolError("접두사는 24자 이하로 입력하세요.")
        module_root = scoped(self.root, "Source", self.module)
        if not (module_root / f"{self.module}.Build.cs").is_file():
            raise ToolError("선택한 프로젝트 Source 모듈의 .Build.cs를 찾을 수 없습니다.\n"
                            "Blueprint 전용 프로젝트는 먼저 C++ 클래스를 추가하세요. 플러그인 모듈은 미지원입니다.")
        relative_dir(self.header_subdir, unreal=True)
        relative_dir(self.json_subdir)
        relative_dir(self.asset_subdir, unreal=True)
        if not self.json_subdir:
            raise ToolError("JSON 하위 경로는 비워 둘 수 없습니다.")
        if self.json_subdir.split("/")[0].casefold() in {"source", "binaries", "intermediate", "plugins", "config"}:
            raise ToolError("JSON은 Source/Binaries/Intermediate/Plugins/Config 외의 폴더에 저장하세요.")
        scoped(self.root, f"Source/{self.module}/Public", "/".join(x for x in (self.header_subdir, self.header_name) if x))
        scoped(self.root, f"Source/{self.module}/Public", "/".join(x for x in (self.header_subdir, "DataTableSubsystem.h") if x))
        scoped(self.root, f"Source/{self.module}/Private", "/".join(x for x in (self.header_subdir, "DataTableSubsystem.cpp") if x))
        inside(self.root, self.json_subdir)
        scoped(self.root, "Content", self.asset_subdir)

    def route_for(self, table: "Table") -> str:
        return relative_dir(self.routes.get(table.name, table.subpath), unreal=True)


def discover_projects(folder: Path) -> list[Path]:
    root = folder.resolve()
    if not root.is_dir():
        raise ToolError("프로젝트 폴더가 없습니다.")
    result = sorted(root.glob("*.uproject"))
    if not result:
        raise ToolError("선택한 폴더 바로 아래에 .uproject가 없습니다. 프로젝트 폴더 자체를 선택하세요.")
    return result


def modules_for(uproject: Path) -> list[str]:
    source = uproject.parent / "Source"
    if not source.is_dir():
        return []
    return sorted(p.parent.name for p in source.glob("*/*.Build.cs") if p.stem == p.parent.name + ".Build")


def register_project(uproject: Path) -> Project:
    uproject = uproject.resolve()
    try:
        descriptor = json.loads(uproject.read_text(encoding="utf-8-sig"))
        if not isinstance(descriptor, dict):
            raise ValueError("프로젝트 descriptor가 객체가 아닙니다.")
    except (OSError, ValueError) as exc:
        raise ToolError(f".uproject를 읽을 수 없습니다: {exc}") from exc
    modules = modules_for(uproject)
    runtime = [m.get("Name") for m in descriptor.get("Modules", []) if m.get("Type") == "Runtime"]
    chosen = next((m for m in runtime if m in modules), modules[0] if modules else "")
    initials = "".join(c for c in uproject.stem if c.isupper())[:8] or "DT"
    return Project(str(uuid.uuid4()), str(uproject), uproject.stem, chosen, initials)


class Registry:
    def __init__(self, home: Path | None = None):
        self.home = home or app_dir()
        self.path = self.home / "projects.json"
        # Import the former app's settings once, only for the default location.
        # Explicit homes are isolated; neither an existing new registry nor the
        # legacy file is overwritten. Share the legacy lock during the copy.
        if (home is None and not os.environ.get("UEROWFORGE_HOME")
                and not os.environ.get("TABLEDESK_HOME") and not self.path.exists()):
            legacy_home = self.home.with_name("UETableDesk")
            legacy_path = legacy_home / "projects.json"
            if legacy_path.is_file():
                with file_lock(legacy_home / "registry.lock"), file_lock(self.home / "registry.lock"):
                    if not self.path.exists():
                        Registry(legacy_home)  # Validate before copying; no recursive migration.
                        atomic_write(self.path, legacy_path.read_bytes())
        self.projects: list[Project] = []
        self._loaded_digest: str | None = None
        if self.path.exists():
            data = self.path.read_bytes()
            try:
                value = json.loads(data)
                if not isinstance(value, dict) or value.get("version") != 1:
                    raise ValueError("지원하지 않는 설정 버전")
                self.projects = [Project(**p) for p in value["projects"]]
            except (ValueError, TypeError, KeyError) as exc:
                raise ToolError(f"설정 파일을 읽지 못했습니다. 원본은 보존합니다: {self.path}\n{exc}") from exc
            self._loaded_digest = digest(data)

    def save(self) -> None:
        self.home.mkdir(parents=True, exist_ok=True)
        with file_lock(self.home / "registry.lock"):
            current = digest(self.path.read_bytes()) if self.path.exists() else None
            if current != self._loaded_digest:
                raise ToolError("다른 프로그램에서 프로젝트 설정이 변경됐습니다. 앱을 다시 실행하세요.")
            data = json_text({"version": 1, "projects": [asdict(p) for p in self.projects]}).encode("utf-8")
            atomic_write(self.path, data)
            self._loaded_digest = digest(data)

    def add(self, project: Project) -> Project:
        for existing in self.projects:
            if Path(existing.uproject).resolve() == Path(project.uproject).resolve():
                return existing
        self.projects.append(project)
        self.save()
        return project

    def remove(self, project_id: str) -> None:
        self.projects = [p for p in self.projects if p.id != project_id]
        self.save()  # Never removes project files.


@contextmanager
def file_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise ToolError(f"다른 변환/설정 저장이 진행 중이거나 이전 잠금이 남아 있습니다.\n"
                        f"UERowForge와 구버전 TableDesk가 모두 종료된 것을 확인한 뒤 이 lock 파일만 제거하세요:\n{path}") from exc
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(f"pid={os.getpid()}\n")
        yield
    finally:
        path.unlink(missing_ok=True)


@dataclass(frozen=True)
class Issue:
    level: str
    source: str
    sheet: str
    cell: str
    message: str

    def __str__(self) -> str:
        return f"[{self.level}] {Path(self.source).name} / {self.sheet} / {self.cell}: {self.message}"


@dataclass(frozen=True)
class Field:
    name: str
    type: str


@dataclass
class Table:
    name: str
    source: str
    sheet: str
    subpath: str
    fields: list[Field]
    rows: list[dict]
    issues: list[Issue] = field(default_factory=list)
    source_sha256: str = ""

    @property
    def valid(self) -> bool:
        return not any(i.level == "오류" for i in self.issues)

    def schema(self) -> list[dict]:
        return [asdict(f) for f in self.fields if f.type != "RowKey"]

    def cpp_name(self, prefix: str) -> str:
        return f"F{prefix}{self.name}Row"


def cell_name(col: int, row: int) -> str:
    letters = ""
    while col:
        col, r = divmod(col - 1, 26)
        letters = chr(65 + r) + letters
    return f"{letters}{row}"


def _blank(value: object) -> bool:
    return value is None or value == ""


def _value(raw: object, typ: str) -> object:
    if isinstance(raw, SpecialCell):
        raise ToolError(f"{raw.kind} 셀은 지원하지 않습니다. 값으로 붙여넣으세요: {raw.text}")
    if typ in ("String", "Name", "RowKey"):
        if _blank(raw):
            if typ == "RowKey":
                raise ToolError("RowName은 필수입니다.")
            return "" if typ == "String" else "None"
        if not isinstance(raw, str):
            raise ToolError("문자열/Name/행 키는 Excel 텍스트 셀로 입력하세요. 앞자리 0 손실을 방지합니다.")
        if typ == "RowKey":
            if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_\-]{0,127}", raw) or raw.casefold() == "none":
                raise ToolError("행 키는 영문/숫자/밑줄/하이픈 1~128자, 'None'은 제외합니다.")
        if typ == "Name" and (len(raw) > 128 or any(ord(c) < 32 for c in raw)):
            raise ToolError("Name은 128자 이하이며 제어 문자를 사용할 수 없습니다.")
        return raw
    if _blank(raw):
        raise ToolError(f"{typ} 값이 비었습니다. 0/false 등을 명시하세요.")
    if typ == "Bool":
        if isinstance(raw, bool):
            return raw
        if raw in (0, 1):
            return bool(raw)
        if isinstance(raw, str) and raw.strip().lower() in ("true", "false", "0", "1"):
            return raw.strip().lower() in ("true", "1")
        raise ToolError("Bool은 TRUE/FALSE 또는 1/0이어야 합니다.")
    if isinstance(raw, bool):
        raise ToolError("숫자 칸에 Bool을 사용할 수 없습니다.")
    try:
        num = Decimal(str(raw).strip())
    except InvalidOperation as exc:
        raise ToolError(f"{typ} 숫자가 아닙니다: {raw!r}") from exc
    if not num.is_finite():
        raise ToolError("NaN/Infinity는 허용하지 않습니다.")
    if typ == "Int":
        if num != num.to_integral_value() or num < -2147483648 or num > 2147483647:
            raise ToolError("Int는 int32 범위의 정수여야 합니다.")
        return int(num)
    if typ == "Float":
        if abs(num) > Decimal("3.4028234663852886e38"):
            raise ToolError("Float의 최대 범위를 초과했습니다.")
        result = float(num)
        if not math.isfinite(result):
            raise ToolError("유한한 실수가 필요합니다.")
        return result
    raise ToolError(f"지원하지 않는 타입: {typ}")


def parse_sheet(sheet: Sheet, source: Path) -> Table:
    name = str(sheet.get(1, 2) or "").strip()
    table = Table(name or sheet.name, str(source.resolve()), sheet.name, "", [], [])

    def error(cell: str, message: str, level: str = "오류") -> None:
        if len(table.issues) < 200:
            table.issues.append(Issue(level, str(source), sheet.name, cell, message))

    if sheet.get(1, 1) != "TableName":
        error("A1", "A1=TableName, B1=테이블명인 템플릿을 사용하세요. 설명 시트는 '_'로 시작하세요.")
    try:
        identifier(name, "테이블명")
    except ToolError as exc:
        error("B1", str(exc))
    if sheet.get(1, 4) not in (None, "", "SubPath"):
        error("D1", "D1은 SubPath 또는 빈 칸이어야 합니다.")
    if not _blank(sheet.get(1, 5)):
        if sheet.get(1, 4) != "SubPath":
            error("D1", "하위 경로를 사용할 때 D1=SubPath를 입력하세요.")
        try:
            table.subpath = relative_dir(str(sheet.get(1, 5)), unreal=True)
        except ToolError as exc:
            error("E1", str(exc))
    if sheet.merged:
        error("시트", "테이블 시트의 병합 셀은 지원하지 않습니다. 셀 병합을 해제하세요.")
    cols = sorted({c for (r, c), v in sheet.cells.items() if r in (2, 3) and not _blank(v)})
    if not cols:
        error("2~3행", "필드명/타입이 없습니다.")
        return table
    last = max(cols)
    seen_fields: set[str] = set()
    for col in range(1, last + 1):
        raw_name = sheet.get(2, col)
        raw_type = sheet.get(3, col)
        field_name = str(raw_name or "").strip()
        typ = TYPES.get(str(raw_type or "").strip().lower(), "")
        try:
            identifier(field_name, "필드명")
        except ToolError as exc:
            error(cell_name(col, 2), str(exc))
        if field_name.casefold() in seen_fields:
            error(cell_name(col, 2), "필드명이 중복됩니다. 대소문자를 구분하지 않습니다.")
        seen_fields.add(field_name.casefold())
        if not typ:
            error(cell_name(col, 3), "지원 타입: RowKey, String, Name, Int, Float, Bool")
        if col == 1 and (field_name != "RowName" or typ != "RowKey"):
            error("A2:A3", "첫 컬럼은 RowName / RowKey여야 합니다.")
        if col > 1 and (typ == "RowKey" or field_name.casefold() == "rowname"):
            error(cell_name(col, 3), "행 키는 첫 컬럼에 한 번만 지정하세요.")
        table.fields.append(Field(field_name, typ))
    if last < 2:
        error("2행", "RowName 외에 데이터 필드가 하나 이상 필요합니다.")
    row_numbers = sorted({r for r, c in sheet.cells if r >= 4})
    seen_keys: set[str] = set()
    for row in row_numbers:
        if all(_blank(sheet.get(row, c)) for c in range(1, last + 1)):
            if any(not _blank(v) for (r, c), v in sheet.cells.items() if r == row and c > last):
                error(f"{row}행", "정의된 컬럼 밖에 값이 있습니다.")
            continue
        values: dict = {}
        for col, fld in enumerate(table.fields, 1):
            if not fld.type:
                continue
            try:
                values[fld.name] = _value(sheet.get(row, col), fld.type)
            except ToolError as exc:
                error(cell_name(col, row), str(exc))
        key = values.get("RowName")
        if isinstance(key, str):
            if key.casefold() in seen_keys:
                error(cell_name(1, row), f"중복 RowName: {key} (대소문자 구분 없음)")
            seen_keys.add(key.casefold())
        table.rows.append(values)
    extra = [(r, c) for (r, c), v in sheet.cells.items() if r >= 4 and c > last and not _blank(v)]
    if extra:
        error(cell_name(extra[0][1], extra[0][0]), "정의된 컬럼 밖에 데이터가 있습니다.")
    if not table.rows:
        error("4행~", "데이터가 없습니다. 빈 테이블로 기존 데이터를 지우는 동작은 이 버전에서 차단합니다.")
    return table


def load_tables(paths: list[Path]) -> tuple[list[Table], list[Issue]]:
    tables: list[Table] = []
    issues: list[Issue] = []
    seen: dict[str, Table] = {}
    for path in dict.fromkeys(Path(p).resolve() for p in paths):
        try:
            if path.stat().st_size > 32 * 1024 * 1024:
                raise ToolError("파일 크기가 32 MiB를 초과합니다.")
            before_signature = digest(path.read_bytes())
            sheets = read_xlsx(path)
            signature = digest(path.read_bytes())
            if signature != before_signature:
                raise ToolError("읽는 도중 원본 엑셀이 변경됐습니다. 저장을 마치고 다시 불러오세요.")
            if not sheets:
                issues.append(Issue("오류", str(path), "", "", "변환할 시트가 없습니다."))
            for sheet in sheets:
                table = parse_sheet(sheet, path)
                table.source_sha256 = signature
                lower = table.name.casefold()
                if lower in seen:
                    issue = Issue("오류", str(path), sheet.name, "B1", f"불러온 파일 간 테이블명 중복: {table.name}")
                    table.issues.append(issue)
                    seen[lower].issues.append(issue)
                else:
                    seen[lower] = table
                tables.append(table)
        except (OSError, ValueError) as exc:
            issues.append(Issue("오류", str(path), "", "", str(exc)))
    return tables, issues


def struct_text(table: Table, project: Project) -> str:
    text = [f"// BEGIN TABLEDESK: {table.name}", "USTRUCT(BlueprintType)",
            f"struct {project.module.upper()}_API {table.cpp_name(project.prefix)} : public FTableRowBase",
            "{", "    GENERATED_BODY()", ""]
    for fld in table.fields:
        if fld.type == "RowKey":
            continue
        typ, default = CPP[fld.type]
        text += [f'    UPROPERTY(BlueprintReadOnly, Category = "{table.name}")',
                 f"    {typ} {fld.name} = {default};", ""]
    text += ["};", f"// END TABLEDESK: {table.name}"]
    return "\n".join(text)


def header_blocks(text: str) -> dict[str, str]:
    pattern = re.compile(r"^// BEGIN TABLEDESK: ([A-Za-z][A-Za-z0-9_]*)\n.*?^// END TABLEDESK: \1$", re.M | re.S)
    found: dict[str, str] = {}
    for match in pattern.finditer(text):
        name = match[1]
        if name.casefold() in {n.casefold() for n in found}:
            raise ToolError("헤더에 중복 자동 생성 구간이 있습니다.")
        found[name] = match[0]
    if text.count("// BEGIN TABLEDESK:") != len(found) or text.count("// END TABLEDESK:") != len(found):
        raise ToolError("헤더의 자동 생성 마커가 손상됐습니다.")
    return found


def merge_header(existing: str | None, tables: list[Table], project: Project) -> str:
    fresh = {t.name: struct_text(t, project) for t in tables}
    if existing is None:
        body = (f'{MARKER}\n// Edit Excel source; only marked blocks are maintained by TableDesk.\n'
                '#pragma once\n\n#include "CoreMinimal.h"\n#include "Engine/DataTable.h"\n'
                f'#include "{project.prefix}StructTypes.generated.h"\n')
        return body + "\n\n" + "\n\n".join(fresh[n] for n in sorted(fresh)) + "\n"
    existing = existing.replace("\r\n", "\n")
    if not existing.startswith(MARKER + "\n"):
        raise ToolError(f"기존 {project.header_name}은 UERowForge 관리 파일이 아닙니다.\n"
                        "자동 수정하지 않습니다. 비어 있는 헤더 하위 경로를 지정하세요.")
    generated = re.findall(r'^\s*#include\s+[<\"]([^>\"]+)[>\"]', existing, re.M)
    if not generated or generated[-1] != f"{project.prefix}StructTypes.generated.h":
        raise ToolError("generated.h include가 없거나 마지막 include가 아닙니다. 헤더를 점검하세요.")
    blocks = header_blocks(existing)
    for name in fresh:
        conflict = next((n for n in blocks if n.casefold() == name.casefold() and n != name), None)
        if conflict:
            raise ToolError(f"테이블 이름의 대소문자만 바꾸는 변경은 지원하지 않습니다: {conflict} → {name}")
    result = existing
    for name, block in fresh.items():
        if name in blocks:
            result = result.replace(blocks[name], block, 1)
        else:
            # Detect a manually defined duplicate even outside owned blocks.
            if re.search(r"\b" + re.escape(f"F{project.prefix}{name}Row") + r"\b", existing):
                raise ToolError(f"같은 구조체 이름이 수기 코드에 있습니다: F{project.prefix}{name}Row")
            result = result.rstrip() + "\n\n" + block + "\n"
    return result


@dataclass
class WriteTask:
    path: Path
    content: bytes
    previous: bytes | None
    label: str

    @property
    def changed(self) -> bool:
        return self.content != self.previous


@dataclass
class Plan:
    project: Project
    tables: list[Table]
    writes: list[WriteTask]
    header_changed: bool
    notes: list[str]
    asset_jobs: list[dict]
    manifest_path: Path

    @property
    def changed(self) -> list[WriteTask]:
        return [w for w in self.writes if w.changed]

    @property
    def code_changed(self) -> bool:
        return any(w.changed for w in self.writes if w.label.startswith("C++"))

    def code_diff(self) -> str:
        parts = []
        for task in self.writes:
            if not task.label.startswith("C++"):
                continue
            before = (task.previous or b"").decode("utf-8-sig").splitlines(keepends=True)
            after = task.content.decode("utf-8-sig").splitlines(keepends=True)
            rel = task.path.relative_to(self.project.root).as_posix()
            diff = "".join(difflib.unified_diff(before, after, fromfile="현재/" + rel, tofile="변환 후/" + rel))
            if diff:
                parts.append(diff)
        return "\n".join(parts) or "C++ 코드 변경 없음"

    def subsystem_preview(self) -> str:
        return "\n\n".join("// " + w.path.relative_to(self.project.root).as_posix() + "\n" + w.content.decode("utf-8-sig")
                           for w in self.writes if w.label.startswith("C++ 서브시스템"))

    def summary(self) -> str:
        lines = [f"프로젝트: {self.project.name}", f"테이블: {', '.join(t.name for t in self.tables)}",
                 f"C++ 코드 {'변경: 에셋 반영 전 C++ Editor 빌드 필요' if self.code_changed else '변경 없음'}", ""]
        for w in self.writes:
            state = "생성" if w.previous is None else "변경" if w.changed else "동일"
            lines.append(f"[{state}] {w.path.relative_to(self.project.root)}")
        lines += ["", "예정 에셋 (변환 버튼은 .uasset을 만들지 않습니다):"]
        lines += ["  " + j["asset_path"] for j in self.asset_jobs]
        lines += ["", "메모:"] + ["  " + n for n in self.notes]
        return "\n".join(lines)

    def header_diff(self) -> str:
        task = next(w for w in self.writes if w.label == "C++ 헤더")
        before = (task.previous or b"").decode("utf-8-sig").splitlines(keepends=True)
        after = task.content.decode("utf-8-sig").splitlines(keepends=True)
        return "".join(difflib.unified_diff(before, after, fromfile="현재 헤더", tofile="변환 후 헤더")) or "헤더 변경 없음"


def _source_files(project: Project):
    """Visit project/module and project-plugin source, never Binaries/Intermediate.

    os.walk does not follow directory symlinks. Linked code is not silently skipped:
    it requires a manual conflict check first, so generation fails closed.
    """
    for base_name in ("Source", "Plugins"):
        base = inside(project.root, base_name)
        if not base.exists():
            continue
        for directory, dirs, files in os.walk(base, followlinks=False):
            dirs[:] = [d for d in dirs if d not in {"Binaries", "Intermediate", "Saved", "Content", ".git"}]
            for d in dirs:
                child = Path(directory) / d
                if child.is_symlink() or (hasattr(child, "is_junction") and child.is_junction()):
                    raise ToolError(f"클래스 충돌 검사 중 링크된 소스 폴더를 발견했습니다. 실제 경로를 확인하세요: {child}")
            for filename in files:
                path = Path(directory) / filename
                if path.suffix.casefold() in {".h", ".hpp", ".cpp", ".inl"}:
                    yield path


def _check_subsystem_conflicts(project: Project, header: Path, source: Path) -> None:
    for path in _source_files(project):
        resolved = path.resolve()
        if path.name.casefold() in {"datatablesubsystem.h", "datatablesubsystem.cpp"}:
            if resolved not in (header, source):
                raise ToolError(f"고정 이름 DataTableSubsystem 파일이 다른 경로에 있습니다. 중복 생성하지 않습니다:\n{path}")
        if path.suffix.casefold() not in {".h", ".hpp", ".inl"} or resolved == header:
            continue
        raw = path.read_bytes()
        if b"UDataTableSubsystem" not in raw:
            continue
        text = raw.decode("utf-8-sig", errors="replace")
        # Remove comments/string literals so documentation and includes don't conflict.
        text = re.sub(r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"', " ", text, flags=re.S)
        if re.search(r"\bclass\s+(?:[A-Za-z_]\w*_API\s+)?UDataTableSubsystem\s*(?:final\s*)?[:{]", text):
            raise ToolError(f"이미 UDataTableSubsystem 클래스가 정의돼 있습니다. 수기 코드/플러그인을 덮어쓰지 않습니다:\n{path}")


def _decode_code(raw: bytes, label: str) -> str:
    try:
        return raw.decode("utf-8-sig").replace("\r\n", "\n")
    except UnicodeError as exc:
        raise ToolError(f"{label}는 UTF-8이어야 합니다. 기존 파일은 변경하지 않습니다.") from exc


def _managed_subsystem_task(path: Path, content: str, state: dict, root: Path, label: str) -> WriteTask:
    prior = path.read_bytes() if path.exists() else None
    relative = path.relative_to(root).as_posix()
    tracked = state.get("managed_files", {}).get(relative)
    if prior is not None:
        text = _decode_code(prior, label)
        if not text.startswith(SUBSYSTEM_MARKER + "\n") or not tracked or digest(text) != tracked:
            raise ToolError(f"기존 서브시스템이 수기 파일이거나 외부에서 변경됐습니다. 덮어쓰기를 차단합니다:\n{path}")
    elif tracked:
        raise ToolError(f"관리 중인 서브시스템 파일이 없어졌습니다. 백업/소스 관리에서 복원하세요:\n{path}")
    payload = prior if prior is not None and text == content else content.encode("utf-8")
    state.setdefault("managed_files", {})[relative] = digest(content)
    return WriteTask(path, payload, prior, label)


def build_plan(project: Project, tables: list[Table]) -> Plan:
    """Plan a selected conversion; an empty conversion is never allowed."""
    if not tables or any(not t.valid for t in tables):
        raise ToolError("정상 검증된 테이블을 하나 이상 선택하세요.")
    return _build_plan(project, tables)


def _build_plan(project: Project, tables: list[Table]) -> Plan:
    """Read-only planning shared with whole-project code preview.

    Only the code-preview adapter calls this with no incoming tables, so it can
    show retained schemas even when no workbook is open. No files are written.
    """
    project.check()
    if any(not t.valid for t in tables):
        raise ToolError("정상 검증된 테이블만 미리 볼 수 있습니다.")
    for table in tables:
        if table.source_sha256 and digest(Path(table.source).read_bytes()) != table.source_sha256:
            raise ToolError(f"불러온 뒤 원본 엑셀이 변경됐습니다. 다시 읽기 / 검증을 누르세요: {table.source}")
    names = [t.name.casefold() for t in tables]
    if len(names) != len(set(names)):
        raise ToolError("테이블 이름이 중복됩니다.")
    header = scoped(project.root, f"Source/{project.module}/Public", "/".join(x for x in (project.header_subdir, project.header_name) if x))
    for existing_header in inside(project.root, "Source").rglob("*.h"):
        if existing_header.name.casefold() == project.header_name.casefold() and existing_header.resolve() != header:
            raise ToolError(f"같은 이름의 헤더가 다른 경로에 있습니다. 중복 생성하지 않습니다:\n{existing_header}\n"
                            "설정의 헤더 경로를 확인하세요. 수기 헤더 자동 편집은 지원하지 않습니다.")
    sub_header = inside(project.root, project.subsystem_header_relative)
    sub_source = inside(project.root, project.subsystem_source_relative)
    _check_subsystem_conflicts(project, sub_header, sub_source)
    old = header.read_bytes() if header.exists() else None
    current_text = _decode_code(old, "행 구조체 헤더") if old is not None else None
    manifest_path = header.parent / MANIFEST
    old_manifest = manifest_path.read_bytes() if manifest_path.exists() else None
    try:
        state = json.loads(old_manifest) if old_manifest else {"version": 1, "tables": {}}
        if not isinstance(state, dict) or state.get("version") != 1 or not isinstance(state.get("tables"), dict):
            raise ValueError("잘못된 생성 이력")
        if not isinstance(state.get("managed_files", {}), dict):
            raise ValueError("잘못된 코드 생성 이력")
        if state.get("generator_revision", 1) not in (1, 2, GENERATOR_REVISION):
            raise ValueError("지원하지 않는 생성기 버전")
    except (ValueError, TypeError) as exc:
        raise ToolError("생성 이력 파일이 손상됐거나 더 최신 버전입니다. 기존 파일은 변경하지 않습니다.") from exc
    if state.get("prefix", project.prefix) != project.prefix or state.get("module", project.module) != project.module:
        raise ToolError("기존 생성 이력의 접두사/모듈과 다릅니다. 기존 타입을 먼저 정리하세요.")
    state.update(prefix=project.prefix, module=project.module)
    previous_blocks = header_blocks(current_text) if current_text else {}
    if current_text and not old_manifest:
        raise ToolError("기존 행 헤더의 생성 이력이 없습니다. .tabledesk-manifest.json을 백업에서 복원하세요.")
    if set(previous_blocks) != set(state["tables"]):
        raise ToolError("행 헤더와 생성 이력의 테이블 목록이 다릅니다. 삭제/수정된 파일을 복원하세요.")
    all_tables: dict[str, Table] = {}
    for name, meta in state["tables"].items():
        if not isinstance(meta, dict) or digest(previous_blocks[name]) != meta.get("block_sha256"):
            raise ToolError(f"{name} 자동 생성 구간이 외부에서 수정/삭제됐습니다. 원본과 비교하세요.")
        try:
            identifier(name, "기존 테이블명")
            fields = [Field("RowName", "RowKey")]
            for f in meta["schema"]:
                identifier(f["name"], "기존 필드명")
                if f["type"] not in CPP:
                    raise ValueError("지원하지 않는 타입")
                fields.append(Field(f["name"], f["type"]))
            if len({f.name.casefold() for f in fields}) != len(fields) or len(fields) < 2:
                raise ValueError("중복/빈 스키마")
        except (KeyError, TypeError, ValueError) as exc:
            raise ToolError(f"{name} 생성 이력 스키마가 손상됐습니다.") from exc
        all_tables[name] = Table(name, "", name, "", fields, [])
    for table in tables:
        identifier(table.name, "테이블명")
        conflict = next((n for n in all_tables if n.casefold() == table.name.casefold() and n != table.name), None)
        if conflict:
            raise ToolError(f"테이블 이름의 대소문자만 바꾸는 변경은 지원하지 않습니다: {conflict} → {table.name}")
        all_tables[table.name] = table
    # Rebuild every tracked schema so the v0.1.x read/write fields migrate together,
    # including tables not selected in this conversion. Unselected JSON is untouched.
    generated_tables = [all_tables[n] for n in sorted(all_tables)]
    content = merge_header(current_text, generated_tables, project)
    payload = old if old is not None and current_text == content else content.encode("utf-8")
    writes = [WriteTask(header, payload, old, "C++ 헤더")]
    notes = ["행 필드는 BlueprintReadOnly + Category로 고정합니다. 관리 중인 모든 행 구조체에 적용합니다.",
             "UDataTableSubsystem: private TObjectPtr + C++/BP 공용 Get<Table>Table()을 생성합니다. 행 조회 래퍼·자체 템플릿은 없습니다.",
             "Getter는 공유 테이블 객체를 반환합니다. 로드 실패 시 nullptr이며, 행 조회·실패 처리와 원본 수정 금지는 호출 측 책임입니다.",
             "선택하지 않은 테이블의 구조체·서브시스템 멤버는 보존합니다. JSON 데이터는 선택 항목만 갱신합니다.",
             "에셋 등록 목록은 UE 에셋 반영이 모두 성공한 뒤 DefaultGame.ini에 갱신합니다. 변환만으로 등록하지 않습니다.",
             "행/필드 삭제는 참조를 자동 이관하지 않습니다. 변경점과 소스 관리를 확인하세요."]
    if state.get("generator_revision", 1) == 1 and old:
        notes.append("v0.1.x 이관: 미선택 테이블을 포함해 행 필드의 편집/쓰기 지정자를 제거합니다. 기존 BP 쓰기 노드와 C++ Editor 빌드를 확인하세요.")
    if state.get("generator_revision", 1) == 2 and state.get("managed_files"):
        notes.append("v0.2.0 이관: 모든 관리 테이블의 Find<Table>Row/TryGet<Table>Row를 제거하고 Get<Table>Table()로 교체합니다. 기존 C++ 호출/BP 노드는 자동 이관하지 않습니다.")
        notes.append("행 타입을 사용하는 C++ 호출 파일은 행 헤더를 직접 include해야 합니다. 서브시스템 헤더는 더 이상 행 헤더를 포함하지 않습니다. Editor 타깃 전체 빌드와 BP 재연결이 필요합니다.")
    jobs: list[dict] = []
    claimed: set[Path] = {header, manifest_path, sub_header, sub_source}
    for table in tables:
        route = project.route_for(table)
        json_rel = "/".join(x for x in (route, table.name + ".json") if x)
        dest = scoped(project.root, project.json_subdir, json_rel)
        if dest in claimed:
            raise ToolError("출력 파일 경로가 서로 충돌합니다.")
        claimed.add(dest)
        prior = dest.read_bytes() if dest.exists() else None
        previous_meta = state["tables"].get(table.name)
        body = json_text(table.rows).encode("utf-8")
        if prior is not None and prior != body:
            owned = previous_meta and previous_meta.get("json_relative") == dest.relative_to(project.root).as_posix()
            if not owned or previous_meta.get("json_sha256") != digest(prior):
                raise ToolError(f"기존 JSON이 수기 파일이거나 외부에서 변경됐습니다. 덮어쓰기를 차단합니다:\n{dest}\n"
                                "원본과 비교한 후 다른 출력 경로를 사용하세요.")
        schema = table.schema()
        if previous_meta:
            prior_fields = {f["name"]: f["type"] for f in previous_meta.get("schema", [])}
            next_fields = {f["name"]: f["type"] for f in schema}
            removed = sorted(set(prior_fields) - set(next_fields))
            retyped = sorted(n for n in prior_fields.keys() & next_fields.keys() if prior_fields[n] != next_fields[n])
            if removed or retyped:
                notes.append(f"주의 {table.name}: 삭제 필드={removed}, 타입 변경={retyped}. 코드/BP 참조 검토 필요.")
            lost_keys = sorted(set(previous_meta.get("row_keys", [])) - {r["RowName"] for r in table.rows})
            if lost_keys:
                notes.append(f"주의 {table.name}: 제거/변경 행 키 {lost_keys[:15]}")
            if (previous_meta.get("json_relative") != dest.relative_to(project.root).as_posix()
                    or previous_meta.get("asset_path") != "/Game/" + "/".join(x for x in (project.asset_subdir, route, "DT_" + table.name) if x)):
                notes.append(f"주의 {table.name}: 출력 경로 변경. 예전 JSON/에셋은 자동 삭제·이동하지 않습니다.")
        writes.append(WriteTask(dest, body, prior, f"JSON {table.name}"))
        asset_child = "/".join(x for x in (project.asset_subdir, route) if x)
        relative_dir(asset_child, unreal=True)
        scoped(project.root, "Content", asset_child)
        asset_path = "/Game/" + "/".join(x for x in (asset_child, "DT_" + table.name) if x)
        jobs.append({"table": table.name, "json_path": str(dest), "json_sha256": digest(body),
                     "struct_path": f"/Script/{project.module}.{project.prefix}{table.name}Row",
                     "asset_path": asset_path, "import_key_field": "RowName",
                     "columns": [f["name"] for f in schema], "row_keys": [r["RowName"] for r in table.rows]})
        state["tables"].setdefault(table.name, {}).update({
            "schema": schema, "json_relative": dest.relative_to(project.root).as_posix(),
            "json_sha256": digest(body), "row_keys": [r["RowName"] for r in table.rows], "asset_path": asset_path})
    for table in generated_tables:
        state["tables"][table.name]["block_sha256"] = digest(struct_text(table, project))
    expected_paths = {p.relative_to(project.root).as_posix() for p in (sub_header, sub_source)}
    if set(state.get("managed_files", {})) - expected_paths:
        raise ToolError("관리 중인 서브시스템 출력 위치가 변경됐습니다. 이전 파일/생성 이력을 함께 이전해야 합니다.")
    writes.append(_managed_subsystem_task(sub_header, subsystem_header(project, generated_tables), state, project.root, "C++ 서브시스템 헤더"))
    writes.append(_managed_subsystem_task(sub_source, subsystem_source(project, generated_tables), state, project.root, "C++ 서브시스템 구현"))
    state["generator_revision"] = GENERATOR_REVISION
    writes.append(WriteTask(manifest_path, json_text(state).encode("utf-8"), old_manifest, "생성 이력"))
    return Plan(project, tables, writes, writes[0].changed, notes, jobs, manifest_path)


def execute_plan(plan: Plan) -> Path | None:
    """Preflight all files, then stage and replace. Back up originals, roll back on
    ordinary write errors. Not a filesystem-wide atomic transaction on power loss.
    """
    root = plan.project.root
    saved = inside(root, "Saved/TableDesk")
    with file_lock(saved / "conversion.lock"):
        plan.project.check()
        _check_subsystem_conflicts(plan.project, inside(root, plan.project.subsystem_header_relative),
                                  inside(root, plan.project.subsystem_source_relative))
        for table in plan.tables:
            if table.source_sha256 and digest(Path(table.source).read_bytes()) != table.source_sha256:
                raise ToolError("미리보기 이후 원본 엑셀이 변경됐습니다. 다시 읽고 변환하세요.")
        for task in plan.writes:
            rel = task.path.relative_to(root).as_posix()
            if inside(root, rel) != task.path:
                raise ToolError("미리보기 이후 출력 경로가 변경됐습니다.")
            now = task.path.read_bytes() if task.path.exists() else None
            if now != task.previous:
                raise ToolError(f"미리보기 이후 파일이 변경됐습니다. 다시 검증하세요: {task.path}")
        changed = plan.changed
        if not changed:
            return None
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8]
        backup = scoped(root, "Saved/TableDesk", "Backups/" + stamp)
        originals = []
        for task in changed:
            if task.previous is not None:
                relative = task.path.relative_to(root).as_posix()
                atomic_write(backup / relative, task.previous)
                originals.append(relative)
        atomic_write(backup / "backup-info.json", json_text({
            "originals": originals,
            "new_files": [w.path.relative_to(root).as_posix() for w in changed if w.previous is None],
            "note": "앱/에디터를 종료하고 originals를 원래 위치에 복사하세요. new_files는 이 작업에서 새로 생성된 파일입니다."
        }).encode("utf-8"))
        applied: list[WriteTask] = []
        try:
            for task in changed:
                atomic_write(task.path, task.content)
                applied.append(task)
        except OSError as exc:
            rollback_errors = []
            for task in reversed(applied):
                try:
                    if task.previous is None:
                        task.path.unlink(missing_ok=True)
                    else:
                        atomic_write(task.path, task.previous)
                except OSError as rollback:
                    rollback_errors.append(str(rollback))
            raise ToolError(f"파일 저장 실패. 기존 파일 복원을 시도했습니다. 백업: {backup}\n{exc}\n"
                            + "\n".join(rollback_errors)) from exc
        return backup
