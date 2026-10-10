"""Run ONLY inside Unreal's Python commandlet, after a full Editor build.

Experimental adapter, checked against Epic's UE 5.7 API docs but not executed
against a real Unreal installation in the prototype authoring environment.
Preflights every table with transient UDataTables before modifying assets.
Saves are per-asset, not a cross-package transaction. Backups are for recovery.
"""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import traceback
import uuid


def sha(data):
    return hashlib.sha256(data).hexdigest()


def under(root, path):
    root = root.resolve()
    result = Path(path).resolve()
    if not result.is_relative_to(root):
        raise RuntimeError("Project containment check failed: " + str(path))
    return result


def main():
    job_path = Path(os.environ.get("UEROWFORGE_JOB") or os.environ["TABLEDESK_JOB"])
    job = json.loads(job_path.read_text(encoding="utf-8"))
    result_path = job_path.parent / "result.json"
    if Path(job["result_path"]).resolve() != result_path.resolve():
        raise RuntimeError("Unexpected result path")
    result = {"ok": False, "saved": [], "backup": ""}
    try:
        import unreal
        for api in ("DataTable", "DataTableFactory", "DataTableFunctionLibrary", "EditorAssetLibrary", "AssetToolsHelpers"):
            if not hasattr(unreal, api):
                raise RuntimeError("Missing Unreal API/plugin: " + api)
        root = Path(job["root"]).resolve()
        engine_root = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).resolve()
        if root != engine_root:
            raise RuntimeError("Wrong project loaded")
        header = under(root, job["header"])
        if sha(header.read_bytes()) != job["header_sha256"]:
            raise RuntimeError("Header changed after job creation")
        for code in job.get("code_files", []):
            if sha(under(root, code["path"]).read_bytes()) != code["sha256"]:
                raise RuntimeError("Generated C++ changed after job creation: " + code["path"])
        library = unreal.DataTableFunctionLibrary
        asset_library = unreal.EditorAssetLibrary
        tools = unreal.AssetToolsHelpers.get_asset_tools()
        prepared = []
        # Phase 1: all validation before touching any existing asset.
        for entry in job["tables"]:
            asset_path = entry["asset_path"]
            if not re.fullmatch(r"/Game/(?:[A-Za-z_][A-Za-z0-9_]*/)*[A-Za-z_][A-Za-z0-9_]*", asset_path):
                raise RuntimeError("Invalid asset path: " + asset_path)
            disk = under(root, root / "Content" / (asset_path[6:] + ".uasset"))
            now = sha(disk.read_bytes()) if disk.exists() else None
            if now != entry["previous_asset_sha256"]:
                raise RuntimeError("Asset changed after confirmation: " + asset_path)
            source = under(root, entry["json_path"])
            if sha(source.read_bytes()) != entry["json_sha256"]:
                raise RuntimeError("JSON changed after conversion: " + str(source))
            struct = unreal.load_object(None, entry["struct_path"])
            if struct is None:
                raise RuntimeError("Row struct not found. Perform a full Editor C++ build: " + entry["struct_path"])
            transient = unreal.DataTable()
            transient.set_editor_property("import_key_field", "RowName")
            transient.set_editor_property("ignore_extra_fields", False)
            transient.set_editor_property("ignore_missing_fields", False)
            if not library.fill_data_table_from_json_file(transient, str(source), struct):
                raise RuntimeError("Transient JSON import failed: " + entry["table"])
            columns = {str(n) for n in library.get_data_table_column_names(transient)}
            if columns != set(entry["columns"]):
                raise RuntimeError("Compiled columns do not match Excel. Rebuild Editor: " + entry["table"])
            keys = {str(n).casefold() for n in library.get_data_table_row_names(transient)}
            if keys != {n.casefold() for n in entry["row_keys"]}:
                raise RuntimeError("Row keys do not match after import: " + entry["table"])
            exists = asset_library.does_asset_exist(asset_path)
            asset = asset_library.load_asset(asset_path) if exists else None
            if exists and (not isinstance(asset, unreal.DataTable) or asset.get_path_name().split(".")[0] != asset_path):
                raise RuntimeError("Existing asset is not the expected DataTable (or is a redirector): " + asset_path)
            if exists:
                current_struct = library.get_data_table_row_struct(asset)
                if current_struct is None or current_struct.get_path_name() != struct.get_path_name():
                    raise RuntimeError("Existing asset uses a different struct; migration is not automatic: " + asset_path)
            if exists != disk.exists():
                raise RuntimeError("Asset registry/disk state differs. Check the project: " + asset_path)
            prepared.append((entry, source, struct, transient, asset, disk))
            unreal.log("[UEROWFORGE] VALIDATED " + entry["table"])
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8]
        backup = under(root, root / "Saved" / "TableDesk" / "AssetBackups" / stamp)
        backup.mkdir(parents=True, exist_ok=True)
        result["backup"] = str(backup)
        for entry, source, struct, transient, asset, disk in prepared:
            for suffix in (".uasset", ".uexp", ".ubulk"):
                original = under(root, disk.with_suffix(suffix))
                if original.exists():
                    copied = backup / original.relative_to(root)
                    copied.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(original, copied)
        (backup / "job.json").write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
        # Phase 2: update/create and save. Failures may leave earlier assets saved.
        for entry, source, struct, transient, asset, disk in prepared:
            asset_path = entry["asset_path"]
            if asset is None:
                factory = unreal.DataTableFactory()
                factory.set_editor_property("struct", struct)
                folder, name = asset_path.rsplit("/", 1)
                asset = tools.create_asset(name, folder, unreal.DataTable, factory)
                if asset is None:
                    raise RuntimeError("Asset creation failed: " + asset_path)
            asset.set_editor_property("import_key_field", "RowName")
            asset.set_editor_property("ignore_extra_fields", False)
            asset.set_editor_property("ignore_missing_fields", False)
            if not library.fill_data_table_from_json_file(asset, str(source), struct):
                raise RuntimeError("Final JSON import failed: " + asset_path)
            if not asset_library.save_loaded_asset(asset, only_if_is_dirty=False):
                raise RuntimeError("Asset save failed: " + asset_path)
            result["saved"].append(asset_path)
            unreal.log("[UEROWFORGE] SAVED " + asset_path)
        result["ok"] = True
    except Exception as exc:
        result["error"] = str(exc)
        result["traceback"] = traceback.format_exc()
        print("[UEROWFORGE] ERROR " + str(exc))
    finally:
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if not result["ok"]:
        raise RuntimeError(result.get("error", "UERowForge failed"))


if __name__ == "__main__":
    main()
