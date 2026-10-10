"""Guarded runtime registration. Committed only after ALL selected assets saved.

Only the marked section of Config/DefaultGame.ini is owned. Other bytes,
comments, encoding and line endings are preserved. Source conversion does not
write this file. The game reads the custom section through GConfig / GGameIni.
"""
from __future__ import annotations
import codecs
import json
import re

from .core import Plan, ToolError, WriteTask, digest, execute_plan, identifier, inside, json_text
from .subsystem_codegen import RUNTIME_SECTION

BEGIN = "; BEGIN TABLEDESK: RUNTIME"
END = "; END TABLEDESK: RUNTIME"


def _decode(raw: bytes) -> tuple[str, str, bytes]:
    for prefix, encoding in ((codecs.BOM_UTF8, "utf-8"), (codecs.BOM_UTF16_LE, "utf-16-le"),
                             (codecs.BOM_UTF16_BE, "utf-16-be")):
        if raw.startswith(prefix):
            return raw[len(prefix):].decode(encoding), encoding, prefix
    return raw.decode("utf-8"), "utf-8", b""


def _asset_object_path(package: str) -> str:
    if not re.fullmatch(r"/Game/(?:[A-Za-z_][A-Za-z0-9_]*/)*[A-Za-z_][A-Za-z0-9_]*", package):
        raise ToolError(f"런타임 등록용 에셋 경로가 올바르지 않습니다: {package}")
    return package + "." + package.rsplit("/", 1)[-1]


def registration_block(tables: dict[str, str]) -> str:
    lines = [BEGIN, "; Generated after successful asset import. Do not edit this block.",
             "[" + RUNTIME_SECTION + "]"]
    for name in sorted(tables):
        identifier(name, "등록 테이블명")
        lines.append(name + "=" + _asset_object_path(tables[name]))
    return "\n".join(lines + [END])


def build_registration_plan(converted: Plan) -> Plan:
    if converted.changed or not converted.asset_jobs:
        raise ToolError("런타임 등록 전에 JSON·C++ 변환을 완료하고 에셋을 선택하세요.")
    project = converted.project
    source_manifest = next(w for w in converted.writes if w.path == converted.manifest_path)
    state = json.loads(source_manifest.content)
    previous_runtime = state.get("runtime_registration", {})
    if not isinstance(previous_runtime, dict) or not isinstance(previous_runtime.get("tables", {}), dict):
        raise ToolError("런타임 등록 이력이 손상됐습니다.")
    registered = dict(previous_runtime.get("tables", {}))
    for entry in converted.asset_jobs:
        registered[entry["table"]] = entry["asset_path"]
    if not set(registered).issubset(state["tables"]):
        raise ToolError("런타임 등록 이력에 생성 이력에 없는 테이블이 있습니다.")
    path = inside(project.root, "Config/DefaultGame.ini")
    previous = path.read_bytes() if path.exists() else None
    try:
        text, encoding, bom = _decode(previous or b"")
    except UnicodeError as exc:
        raise ToolError("DefaultGame.ini는 UTF-8 또는 BOM이 있는 UTF-16이어야 합니다. 기존 파일은 보존합니다.") from exc
    newline = "\r\n" if "\r\n" in text else "\n"
    pattern = re.compile(r"^" + re.escape(BEGIN) + r"\r?\n.*?^" + re.escape(END) + r"(?=\r?$)", re.M | re.S)
    matches = list(pattern.finditer(text))
    if text.count(BEGIN) != len(matches) or text.count(END) != len(matches) or len(matches) > 1:
        raise ToolError("DefaultGame.ini의 TableDesk 등록 마커가 손상되거나 중복됐습니다.")
    if matches:
        match = matches[0]
        owned = match.group(0).replace("\r\n", "\n")
        if digest(owned) != previous_runtime.get("block_sha256"):
            raise ToolError("DefaultGame.ini의 TableDesk 등록 구역이 외부에서 수정됐거나 소유 이력이 없습니다.")
        outside = text[:match.start()] + text[match.end():]
    else:
        if previous_runtime:
            raise ToolError("기존 런타임 등록 구역이 없어졌습니다. DefaultGame.ini/생성 이력을 복원하세요.")
        outside = text
    if re.search(r"^\s*\[" + re.escape(RUNTIME_SECTION) + r"\]\s*$", outside, re.I | re.M):
        raise ToolError("기존 수기 UETableDesk.DataTables 섹션과 충돌합니다. 자동 덮어쓰기를 차단합니다.")
    block = registration_block(registered)
    formatted = block.replace("\n", newline)
    if matches:
        result = text[:match.start()] + formatted + text[match.end():]
    else:
        separator = ("" if not text else newline if text.endswith(("\n", "\r")) else newline * 2)
        result = text + separator + formatted + newline
    payload = bom + result.encode(encoding)
    state["runtime_registration"] = {"tables": registered, "block_sha256": digest(block)}
    # Unchanged generated files are read dependencies. execute_plan rechecks them
    # after the engine exits, before changing the config or ownership manifest.
    tasks = [WriteTask(w.path, w.content, w.previous, w.label)
             for w in converted.writes if w.path != converted.manifest_path]
    tasks += [WriteTask(path, payload, previous, "런타임 등록 설정"),
              WriteTask(converted.manifest_path, json_text(state).encode("utf-8"), source_manifest.previous, "생성 이력")]
    return Plan(project, converted.tables, tasks, False,
                ["UE 에셋 저장 성공 후에만 적용. 다른 INI 설정은 보존합니다."],
                converted.asset_jobs, converted.manifest_path)


def commit_registration(registration: Plan, saved: list[str]):
    expected = [j["asset_path"] for j in registration.asset_jobs]
    if len(saved) != len(expected) or set(saved) != set(expected):
        raise ToolError("일부 에셋만 저장됐습니다. 런타임 등록 목록은 변경하지 않습니다.")
    for package in expected:
        _asset_object_path(package)
        asset = inside(registration.project.root, "Content/" + package[6:] + ".uasset")
        if not asset.is_file():
            raise ToolError(f"저장 결과의 에셋 파일을 찾지 못했습니다. 런타임 등록을 중단합니다: {asset}")
    return execute_plan(registration)
