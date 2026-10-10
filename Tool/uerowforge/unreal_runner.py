"""Opt-in Unreal invocation followed by guarded runtime registration. No auto build."""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import uuid
from .runtime_registration import build_registration_plan, commit_registration
from .core import Plan, ToolError, app_dir, atomic_write, digest, file_lock, inside, json_text


def resource_root() -> Path:
    # PyInstaller sets __file__ beneath its resource directory as well.
    return Path(__file__).resolve().parent.parent


def check_engine(plan: Plan) -> Path:
    descriptor = json.loads(Path(plan.project.uproject).read_text(encoding="utf-8-sig"))
    if descriptor.get("UERowForgeDemo") or descriptor.get("TableDeskDemo"):
        raise ToolError("샘플 프로젝트는 파일 변환 테스트 전용입니다. 실제 언리얼 프로젝트가 아닙니다.")
    cmd = Path(plan.project.engine_cmd)
    if not cmd.is_file() or cmd.name.lower() not in ("unrealeditor-cmd.exe", "unrealeditor-cmd"):
        raise ToolError("프로젝트 설정에서 UnrealEditor-Cmd.exe를 지정하세요.")
    plugins = {p.get("Name"): p.get("Enabled") for p in descriptor.get("Plugins", [])}
    disabled = [name for name in ("PythonScriptPlugin", "EditorScriptingUtilities") if plugins.get(name) is False]
    if disabled:
        raise ToolError("프로젝트에서 비활성화된 플러그인이 있습니다: " + ", ".join(disabled))
    # Unknown/inherited plugin states are checked again by the engine invocation.
    if plan.changed:
        raise ToolError("먼저 JSON·C++ 코드 변환을 완료하세요. 현재 원본/설정과 출력 파일이 다릅니다.")
    return cmd


def run_assets(plan: Plan, on_log) -> dict:
    cmd = check_engine(plan)
    registration = build_registration_plan(plan)  # Preflight before UE can modify assets.
    home = app_dir() / "jobs" / uuid.uuid4().hex
    home.mkdir(parents=True, exist_ok=True)
    job_path, result_path = home / "job.json", home / "result.json"
    header = next(w for w in plan.writes if w.label == "C++ 헤더")
    job = {"version": 1, "root": str(plan.project.root), "uproject": plan.project.uproject,
           "header": str(header.path), "header_sha256": digest(header.path.read_bytes()),
           "result_path": str(result_path), "tables": [dict(j) for j in plan.asset_jobs],
           "code_files": [{"path": str(w.path), "sha256": digest(w.content)}
                          for w in plan.writes if w.label.startswith("C++")],
           "note": "User confirms a full Editor build and all project editors are closed."}
    for entry in job["tables"]:
        disk = inside(plan.project.root, "Content/" + entry["asset_path"][6:] + ".uasset")
        entry["previous_asset_sha256"] = digest(disk.read_bytes()) if disk.exists() else None
    atomic_write(job_path, json_text(job).encode("utf-8"))
    env = os.environ.copy()
    env["UEROWFORGE_JOB"] = str(job_path)
    bridge = resource_root() / "uerowforge" / "unreal_bridge.py"
    env["UEROWFORGE_BRIDGE"] = str(bridge)
    # No spaces in the -script argument; the external path travels via env instead
    # of relying on Unreal's nested command-line quoting on Windows.
    bootstrap = "__import__('runpy').run_path(__import__('os').environ['UEROWFORGE_BRIDGE'],run_name='__main__')"
    command = [str(cmd), plan.project.uproject, "-run=pythonscript", "-script=" + bootstrap,
               "-unattended", "-nop4", "-nosplash", "-stdout", "-FullStdOutLogOutput", "-UTF8Output"]
    on_log("언리얼 에셋 반영 시작. 로그: " + str(home / "engine.log"))
    kwargs = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    with file_lock(inside(plan.project.root, "Saved/TableDesk/conversion.lock")):
        with (home / "engine.log").open("w", encoding="utf-8") as log:
            with subprocess.Popen(command, cwd=plan.project.root, env=env, shell=False,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  text=True, encoding="utf-8", errors="replace", **kwargs) as proc:
                assert proc.stdout is not None
                for line in proc.stdout:
                    log.write(line)
                    if "UEROWFORGE" in line or "TABLEDESK" in line or "Error" in line or "error" in line:
                        on_log(line.rstrip())
                code = proc.wait()
    if not result_path.exists():
        raise ToolError(f"언리얼이 결과를 반환하지 않았습니다 (exit={code}).\n"
                        f"Python/Editor Scripting Utilities 활성화 및 프로젝트 빌드를 확인하세요.\n로그: {home / 'engine.log'}")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if code != 0 or not result.get("ok"):
        raise ToolError(f"에셋 반영 실패 또는 일부 반영: {result.get('error', '')}\n"
                        f"이미 저장된 에셋: {result.get('saved', [])}\n"
                        f"결과/로그: {home}\n백업: {result.get('backup', '없음')}")
    try:
        backup = commit_registration(registration, result.get("saved", []))
    except (OSError, ValueError) as exc:
        raise ToolError(f"에셋은 저장됐지만 런타임 등록은 완료되지 않았습니다: {exc}\n"
                        f"저장된 에셋: {result.get('saved', [])}\n에셋 백업: {result.get('backup', '')}") from exc
    result["registration_path"] = str(plan.project.root / "Config/DefaultGame.ini")
    result["registration_backup"] = str(backup) if backup else ""
    on_log("런타임 등록 완료: " + result["registration_path"])
    on_log("패키징 쿠킹 규칙은 이번 버전에서 자동 변경하지 않습니다. 생성된 테이블 폴더의 쿠킹 포함 여부를 확인하세요.")
    return result
