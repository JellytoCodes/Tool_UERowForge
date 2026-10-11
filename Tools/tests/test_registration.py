"""Code paths and guarded one-time legacy INI migration; no Unreal execution."""
import codecs
from dataclasses import asdict
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from test_core import fixture, SAMPLE
from uerowforge.core import ToolError, build_plan, digest, execute_plan, json_text, load_tables
from uerowforge.runtime_registration import BEGIN, END


class CodePathTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = fixture(Path(self.temp.name) / "Project")
        self.tables, issues = load_tables([SAMPLE])
        self.assertFalse(issues)
        self.ini = self.project.root / "Config/DefaultGame.ini"

    def tearDown(self):
        self.temp.cleanup()

    def convert(self, tables=None):
        plan = build_plan(self.project, self.tables if tables is None else tables)
        execute_plan(plan)
        return plan

    def snapshot(self, paths):
        return {p: (p.read_bytes(), p.stat().st_mtime_ns) if p.exists() else None for p in paths}

    def install_ini_history(self, revision=4, encoding="utf-8", bom=b"", newline="\n", registered=None):
        plan = self.convert()
        state = json.loads(plan.manifest_path.read_bytes())
        registered = registered if registered is not None else {n: m["asset_path"] for n, m in state["tables"].items()}
        # Reconstruct the previous v3/v4 source format in this temp project.
        path = self.project.root / self.project.subsystem_source_relative
        source = path.read_text().replace(
            "// Auto-generated. Create matching DataTable assets at these paths before play.",
            "// Auto-generated. Planned paths are registered during code/JSON conversion; create matching assets before play.")
        source = source.replace('#include "UObject/UObjectGlobals.h"',
                                '#include "CoreGlobals.h"\n#include "Misc/ConfigCacheIni.h"\n#include "UObject/UObjectGlobals.h"')
        source = source.replace(
            "LoadTable(const TCHAR* TableName, const TCHAR* AssetPath, const UScriptStruct* ExpectedRowStruct)\n    {\n        if (!AssetPath || !*AssetPath)",
            'LoadRegisteredTable(const TCHAR* TableName, const UScriptStruct* ExpectedRowStruct)\n    {\n        FString AssetPath;\n'
            '        if (!GConfig || !GConfig->GetString(TEXT("UETableDesk.DataTables"), TableName, AssetPath, GGameIni)\n'
            '            || AssetPath.IsEmpty())')
        source = source.replace('UE_LOG(LogTableDeskData, Error, TEXT("Missing generated asset path for %s"), TableName);',
                                'UE_LOG(LogTableDeskData, Warning, TEXT("Table %s is not registered. Convert its source with UERowForge first."), TableName);')
        source = source.replace("LoadObject<UDataTable>(nullptr, AssetPath)", "LoadObject<UDataTable>(nullptr, *AssetPath)")
        source = source.replace("TableName, AssetPath);", "TableName, *AssetPath);")
        source = re.sub(r'LoadTable\((TEXT\("[^"]+"\)), TEXT\("[^"]+"\), ', r'LoadRegisteredTable(\1, ', source)
        source = source.replace(
            "// Synchronous loads finish before Initialize returns; getters never start a load.\n"
            "    // Other GameInstance subsystems consuming these tables in Initialize must declare InitializeDependency<UDataTableSubsystem>().",
            "// Small master tables are synchronously loaded once per GameInstance.")
        if revision == 3:
            source = source.replace(
                "// Auto-generated. Planned paths are registered during code/JSON conversion; create matching assets before play.",
                "// Auto-generated. Registration is committed after successful UE asset import.")
            source = source.replace("Convert its source with UERowForge first.", "Import its asset with TableDesk first.")
        self.assertIn("GConfig->GetString", source)
        self.assertNotIn("LoadTable(", source)
        path.write_bytes(source.encode())
        state["managed_files"][self.project.subsystem_source_relative] = digest(source)
        state["generator_revision"] = revision
        comment = ("; Generated after successful asset import. Do not edit this block." if revision == 3 else
                   "; Planned asset paths only; asset readiness is not verified. Do not edit this block.")
        block = "\n".join([BEGIN, comment, "[UETableDesk.DataTables]"] +
                          [f"{name}={package}.{package.rsplit('/', 1)[-1]}" for name, package in sorted(registered.items())] + [END])
        state["runtime_registration"] = {"tables": registered, "block_sha256": digest(block)}
        plan.manifest_path.write_bytes(json_text(state).encode())
        self.ini.parent.mkdir(exist_ok=True)
        prefix = "; 사용자 설정" + newline + "[Other]" + newline + "Keep=1" + newline + newline
        suffix = newline + "; keep following settings" + newline + "[After]" + newline + "Value=2" + newline
        self.ini.write_bytes(bom + (prefix + block.replace("\n", newline) + suffix).encode(encoding))
        return plan, bom + (prefix + suffix[len(newline):]).encode(encoding)

    def test_no_assets_or_ini_required_and_preview_is_read_only(self):
        plan = build_plan(self.project, self.tables)
        self.assertIn('TEXT("/Game/DataTables/DT_Players.DT_Players")', plan.subsystem_preview())
        self.assertFalse(any(w.path.suffix == ".ini" for w in plan.writes))
        self.assertFalse(self.ini.exists())
        self.assertFalse((self.project.root / "Saved").exists())
        execute_plan(plan)
        self.assertFalse(self.ini.exists())
        self.assertFalse(list(self.project.root.rglob("*.uasset")))
        self.assertFalse(list(self.project.root.rglob("*.umap")))

    def test_idempotent_conversion_never_writes_output_or_backup(self):
        first = self.convert()
        before = self.snapshot([w.path for w in first.writes])
        backups = list((self.project.root / "Saved/TableDesk/Backups").iterdir())
        plan = build_plan(self.project, self.tables)
        self.assertFalse(plan.changed)
        with patch("uerowforge.core.atomic_write") as write:
            self.assertIsNone(execute_plan(plan))
            write.assert_not_called()
        self.assertEqual(before, self.snapshot(before))
        self.assertEqual(backups, list((self.project.root / "Saved/TableDesk/Backups").iterdir()))

    def test_excel_hp_change_updates_only_json_and_manifest(self):
        workbook = Path(self.temp.name) / "Input.xlsx"
        workbook.write_bytes(SAMPLE.read_bytes())
        tables, _ = load_tables([workbook])
        self.assertEqual(tables[0].rows[0]["MaxHP"], 100)
        self.ini.parent.mkdir()
        self.ini.write_bytes(b"[Other]\r\nKeep=1\r\n")
        first = self.convert(tables)
        before = self.snapshot([w.path for w in first.writes] + [self.ini])
        with ZipFile(workbook) as archive:
            entries = [(info, archive.read(info.filename)) for info in archive.infolist()]
        ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        with ZipFile(workbook, "w") as archive:
            for info, data in entries:
                if info.filename == "xl/worksheets/sheet2.xml":
                    xml = ET.fromstring(data)
                    value = xml.find(".//m:c[@r='E4']/m:v", ns)
                    self.assertEqual(value.text, "100")
                    value.text = "150"
                    data = ET.tostring(xml, encoding="utf-8")
                archive.writestr(info, data)
        tables, issues = load_tables([workbook])
        self.assertFalse(issues)
        self.assertTrue(all(t.valid for t in tables))
        self.assertEqual(tables[0].rows[0]["MaxHP"], 150)
        plan = build_plan(self.project, [tables[0]])
        self.assertEqual({w.label for w in plan.changed}, {"JSON Players", "생성 이력"})
        execute_plan(plan)
        self.assertEqual(json.loads((self.project.root / "DataTable/Players.json").read_bytes())[0]["MaxHP"], 150)
        unchanged = [w.path for w in plan.writes if not w.changed] + [self.project.root / "DataTable/Items.json", self.ini]
        self.assertEqual({p: before[p] for p in unchanged}, self.snapshot(unchanged))

    def test_normal_conversion_does_not_read_or_write_user_ini(self):
        self.ini.parent.mkdir()
        # Even a legacy-looking manual section and non-UTF8 bytes are user data.
        raw = '[UETableDesk.DataTables]\r\nPlayers=/Manual\r\n; 한글 설정'.encode("cp949")
        self.ini.write_bytes(raw)
        before = self.snapshot([self.ini])
        read = Path.read_bytes
        def guarded(path):
            if path == self.ini:
                raise AssertionError("Normal conversion must not read the INI")
            return read(path)
        with patch.object(Path, "read_bytes", guarded):
            self.convert()
            self.project.routes["Players"] = "Other"
            self.convert([self.tables[0]])
        self.assertEqual(before, self.snapshot([self.ini]))

    def test_selected_path_change_changes_only_cpp_json_and_manifest(self):
        first = self.convert()
        unchanged = self.snapshot([w.path for w in first.writes if w.label in ("C++ 헤더", "C++ 서브시스템 헤더", "JSON Items")])
        old_json = self.project.root / "DataTable/Players.json"
        old_bytes = old_json.read_bytes()
        self.project.routes["Players"] = "NewFolder"
        self.project.routes["Items"] = "UnselectedSetting"
        plan = build_plan(self.project, [self.tables[0]])
        self.assertEqual({w.label for w in plan.changed}, {"C++ 서브시스템 구현", "JSON Players", "생성 이력"})
        self.assertIn('TEXT("/Game/DataTables/NewFolder/DT_Players.DT_Players")', plan.subsystem_preview())
        self.assertIn('TEXT("/Game/DataTables/DT_Items.DT_Items")', plan.subsystem_preview())
        settings = asdict(self.project)
        execute_plan(plan)
        self.assertEqual(unchanged, self.snapshot(unchanged))
        self.assertEqual(old_bytes, old_json.read_bytes())
        self.assertEqual(settings, asdict(self.project))

    def test_invalid_or_missing_retained_paths_block_code_generation(self):
        first = self.convert()
        original = first.manifest_path.read_bytes()
        for package in (None, '/Game/Data/Bad"Path', "/Other/DT_Items"):
            with self.subTest(package=package):
                state = json.loads(original)
                if package is None:
                    state["tables"]["Items"].pop("asset_path")
                else:
                    state["tables"]["Items"]["asset_path"] = package
                first.manifest_path.write_bytes(json_text(state).encode())
                with self.assertRaises(ToolError):
                    build_plan(self.project, [self.tables[0]])

    def test_revision3_and4_migrate_owned_ini_once_and_preserve_encoding(self):
        for revision, encoding, bom, newline in ((3, "utf-8", codecs.BOM_UTF8, "\r\n"),
                                                (4, "utf-16-le", codecs.BOM_UTF16_LE, "\r\n"),
                                                (4, "utf-16-be", codecs.BOM_UTF16_BE, "\n")):
            with self.subTest(revision=revision, encoding=encoding):
                self.project = fixture(Path(self.temp.name) / f"Project{revision}{encoding}")
                self.ini = self.project.root / "Config/DefaultGame.ini"
                old, expected_ini = self.install_ini_history(revision, encoding, bom, newline)
                before = self.snapshot([w.path for w in old.writes] + [self.ini])
                plan = build_plan(self.project, [self.tables[0]])
                self.assertEqual({w.label for w in plan.changed}, {"C++ 서브시스템 구현", "구버전 INI 정리", "생성 이력"})
                self.assertIn("-Players=", plan.legacy_config_diff())
                backup = execute_plan(plan)
                self.assertEqual(expected_ini, self.ini.read_bytes())
                self.assertEqual(before[self.ini][0], (backup / "Config/DefaultGame.ini").read_bytes())
                self.assertNotIn("runtime_registration", json.loads(plan.manifest_path.read_bytes()))
                self.assertIn('TEXT("/Game/DataTables/DT_Items.DT_Items")', plan.subsystem_preview())
                repeat = build_plan(self.project, self.tables)
                self.assertFalse(repeat.changed)
                self.assertFalse(any(w.path.suffix == ".ini" for w in repeat.writes))
                self.assertEqual(before[self.project.root / self.project.header_relative],
                                 self.snapshot([self.project.root / self.project.header_relative])[self.project.root / self.project.header_relative])

    def test_legacy_unselected_registered_route_survives_migration(self):
        self.install_ini_history(registered={"Items": "/Game/PreviouslyImported/DT_Items"})
        plan = build_plan(self.project, [self.tables[0]])
        self.assertIn('TEXT("/Game/PreviouslyImported/DT_Items.DT_Items")', plan.subsystem_preview())
        self.assertIn('TEXT("/Game/DataTables/DT_Players.DT_Players")', plan.subsystem_preview())
        execute_plan(plan)
        self.assertFalse(build_plan(self.project, [self.tables[0]]).changed)

    def test_appended_legacy_block_removal_restores_original_ini(self):
        self.install_ini_history()
        raw = self.ini.read_bytes()
        block = raw[raw.index(BEGIN.encode()):raw.index(END.encode()) + len(END)]
        original = b"[Other]\r\nKeep=1\r\n"
        self.ini.write_bytes(original + b"\r\n" + block.replace(b"\n", b"\r\n") + b"\r\n")
        self.convert()
        self.assertEqual(original, self.ini.read_bytes())

    def test_external_owned_ini_edit_blocks_migration_without_writes(self):
        old, _ = self.install_ini_history()
        self.ini.write_bytes(self.ini.read_bytes().replace(b"Players=/Game", b"Players=/Fake"))
        before = self.snapshot([w.path for w in old.writes] + [self.ini])
        with self.assertRaisesRegex(ToolError, "외부에서 수정"):
            build_plan(self.project, self.tables)
        self.assertEqual(before, self.snapshot(before))

    def test_missing_duplicate_or_broken_legacy_block_is_blocked(self):
        self.install_ini_history()
        raw = self.ini.read_bytes()
        for data in (b"[Other]\nKeep=1\n", raw + raw, raw.replace(END.encode(), b"; broken")):
            with self.subTest(data=data[:20]):
                self.ini.write_bytes(data)
                with self.assertRaises(ToolError):
                    build_plan(self.project, self.tables)

    def test_legacy_ini_changed_after_preview_blocks_every_write(self):
        old, _ = self.install_ini_history()
        plan = build_plan(self.project, self.tables)
        self.ini.write_bytes(self.ini.read_bytes() + b"\n[OtherRace]\nValue=1\n")
        before = self.snapshot([w.path for w in old.writes] + [self.ini])
        with self.assertRaisesRegex(ToolError, "미리보기 이후"):
            execute_plan(plan)
        self.assertEqual(before, self.snapshot(before))

    def test_migration_save_failure_restores_ini_cpp_and_manifest(self):
        from uerowforge import core
        old, _ = self.install_ini_history()
        plan = build_plan(self.project, self.tables)
        before = self.snapshot([w.path for w in old.writes] + [self.ini])
        write = core.atomic_write
        for target in (self.ini, plan.manifest_path):
            with self.subTest(target=target):
                def fail(path, data):
                    if path == target:
                        raise OSError("simulated migration failure")
                    return write(path, data)
                with patch("uerowforge.core.atomic_write", side_effect=fail):
                    with self.assertRaisesRegex(ToolError, "복원을 시도"):
                        execute_plan(plan)
                self.assertEqual({p: v[0] for p, v in before.items()}, {p: p.read_bytes() for p in before})

    def test_legacy_ini_cleanup_cannot_overlap_code(self):
        self.install_ini_history()
        header = self.project.root / self.project.header_relative
        with patch("uerowforge.runtime_registration.scoped", return_value=header):
            with self.assertRaises(ToolError):
                build_plan(self.project, self.tables)

    def test_legacy_ini_symlink_escape_is_blocked(self):
        self.install_ini_history()
        outside = Path(self.temp.name) / "outside.ini"
        outside.write_bytes(self.ini.read_bytes())
        self.ini.unlink()
        try:
            self.ini.symlink_to(outside)
        except OSError:
            self.skipTest("Symlink unavailable")
        before = outside.read_bytes()
        with self.assertRaises(ToolError):
            build_plan(self.project, self.tables)
        self.assertEqual(before, outside.read_bytes())

    def test_normal_conversion_preserves_existing_assets_and_maps(self):
        asset = self.project.root / "Content/DataTables/DT_Players.uasset"
        asset.parent.mkdir(parents=True)
        asset.write_bytes(b"test sentinel; not an Unreal package")
        level = self.project.root / "Content/Existing.umap"
        level.write_bytes(b"test sentinel; not an Unreal map")
        before = self.snapshot([asset, level])
        self.convert()
        self.project.routes["Players"] = "Other"
        self.convert([self.tables[0]])
        self.assertEqual(before, self.snapshot(before))
        self.assertEqual({asset, level}, {p for p in self.project.root.rglob("*") if p.suffix in (".uasset", ".umap")})
