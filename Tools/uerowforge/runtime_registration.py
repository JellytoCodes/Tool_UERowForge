"""One-time removal of owned legacy INI registrations. No runtime registration.

Normal conversion never reads the INI. Only histories with runtime_registration
enter this migration, preserving user settings, encoding and line ending style.
"""
from __future__ import annotations
import codecs
import re

from .core import Project, ToolError, WriteTask, asset_object_path, digest, scoped

BEGIN = "; BEGIN TABLEDESK: RUNTIME"
END = "; END TABLEDESK: RUNTIME"


def _decode(raw: bytes) -> tuple[str, str, bytes]:
    for prefix, encoding in ((codecs.BOM_UTF8, "utf-8"), (codecs.BOM_UTF16_LE, "utf-16-le"),
                             (codecs.BOM_UTF16_BE, "utf-16-be")):
        if raw.startswith(prefix):
            return raw[len(prefix):].decode(encoding), encoding, prefix
    return raw.decode("utf-8"), "utf-8", b""


def remove_legacy_registration(project: Project, state: dict) -> WriteTask | None:
    if "runtime_registration" not in state:
        return None
    previous_runtime = state["runtime_registration"]
    if (not isinstance(previous_runtime, dict) or not isinstance(previous_runtime.get("tables"), dict)
            or not set(previous_runtime["tables"]).issubset(state["tables"])):
        raise ToolError("구버전 런타임 등록 이력이 손상됐습니다.")
    for package in previous_runtime["tables"].values():
        asset_object_path(package)
    path = scoped(project.root, "Config", "DefaultGame.ini")
    previous = path.read_bytes() if path.exists() else None
    try:
        text, encoding, bom = _decode(previous or b"")
    except UnicodeError as exc:
        raise ToolError("DefaultGame.ini 이관은 UTF-8 또는 BOM이 있는 UTF-16만 지원합니다. 기존 파일은 보존합니다.") from exc
    pattern = re.compile(r"^" + re.escape(BEGIN) + r"\r?\n.*?^" + re.escape(END) + r"(?=\r?$)", re.M | re.S)
    matches = list(pattern.finditer(text))
    if text.count(BEGIN) != len(matches) or text.count(END) != len(matches) or len(matches) > 1:
        raise ToolError("DefaultGame.ini의 구버전 등록 마커가 손상되거나 중복됐습니다.")
    if not matches:
        raise ToolError("구버전 등록 구역이 없어졌습니다. DefaultGame.ini/생성 이력을 복원하세요.")
    match = matches[0]
    if digest(match.group(0).replace("\r\n", "\n")) != previous_runtime.get("block_sha256"):
        raise ToolError("DefaultGame.ini의 구버전 등록 구역이 외부에서 수정됐거나 소유 이력이 없습니다.")
    end = match.end()
    # Remove the marker's whole line, including its terminator.
    if text[end:].startswith("\r\n"):
        end += 2
    elif text[end:].startswith("\n"):
        end += 1
    prefix, suffix = text[:match.start()], text[end:]
    # The old writer appended one blank separator before an EOF registration.
    # Remove that separator too; never trim user sections following the block.
    if not suffix:
        newline = "\r\n" if prefix.endswith("\r\n") else "\n"
        if prefix.endswith(newline * 2):
            prefix = prefix[:-len(newline)]
    result = prefix + suffix
    state.pop("runtime_registration")
    return WriteTask(path, bom + result.encode(encoding), previous, "구버전 INI 정리")
