"""Source-package checks only. These tests do NOT build or execute Unreal."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest

from tabledesk.core import build_plan, load_tables, register_project
from tabledesk.runtime_registration import build_registration_plan, commit_registration
from tabledesk.core import ToolError

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_ROOT = ROOT / "Samples/TableDeskSample"


class UnrealSampleSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "different checkout" / "TableDeskSample"
        shutil.copytree(SAMPLE_ROOT, self.root, ignore=shutil.ignore_patterns(
            "Binaries", "Intermediate", "Saved", "DerivedDataCache", ".vs"))
        self.project = register_project(self.root / "TableDeskSample.uproject")
        self.tables, issues = load_tables([self.root / "Excel/TableTemplate.xlsx"])
        self.assertFalse(issues)
        self.assertTrue(all(t.valid for t in self.tables))

    def tearDown(self):
        self.temp.cleanup()

    def test_engine_module_and_real_build_rules_are_present(self):
        data = json.loads(Path(self.project.uproject).read_text())
        self.assertEqual(data["EngineAssociation"], "5.8")
        self.assertNotIn("TableDeskDemo", data)
        self.assertEqual(data["Modules"][0]["Name"], "TableDeskSample")
        for filename, target_type in (("TableDeskSample", "Game"), ("TableDeskSampleEditor", "Editor")):
            text = (self.root / f"Source/{filename}.Target.cs").read_text()
            self.assertIn(f"class {filename}Target : TargetRules", text)
            self.assertIn(f"Type = TargetType.{target_type}", text)
            self.assertIn('ExtraModuleNames.Add("TableDeskSample")', text)
        rules = (self.root / "Source/TableDeskSample/TableDeskSample.Build.cs").read_text()
        for dependency in ('"Core"', '"CoreUObject"', '"Engine"'):
            self.assertIn(dependency, rules)
        module = (self.root / "Source/TableDeskSample/Private/TableDeskSample.cpp").read_text()
        self.assertIn("IMPLEMENT_PRIMARY_GAME_MODULE", module)

    def test_automatic_project_settings_match_shipped_generated_files(self):
        self.assertEqual(self.project.prefix, "TDS")
        self.assertEqual(self.project.header_relative, "Source/TableDeskSample/Public/Data/TDSStructTypes.h")
        self.assertEqual(self.project.json_subdir, "DataTable")
        self.assertEqual(self.project.asset_subdir, "DataTables")
        self.assertTrue(all(self.project.route_for(t) == "" for t in self.tables))
        self.assertFalse(build_plan(self.project, self.tables).changed)

    def test_manifest_is_portable_not_bound_to_original_checkout(self):
        plan = build_plan(self.project, self.tables)
        raw = plan.manifest_path.read_text()
        self.assertNotIn("/mnt/data", raw)
        self.assertNotIn(str(SAMPLE_ROOT), raw)
        state = json.loads(raw)
        self.assertEqual(state["generator_revision"], 3)
        self.assertNotIn("runtime_registration", state)
        for name, entry in state["tables"].items():
            self.assertEqual(entry["json_relative"], f"DataTable/{name}.json")
            self.assertEqual(entry["asset_path"], f"/Game/DataTables/DT_{name}")

    def test_data_only_change_does_not_modify_cpp_or_registration(self):
        table = next(t for t in self.tables if t.name == "Players")
        table.rows[0]["MaxHP"] = 150
        before = (self.root / "Config/DefaultGame.ini").read_bytes()
        plan = build_plan(self.project, [table])
        self.assertFalse(plan.code_changed)
        self.assertEqual({w.label for w in plan.changed}, {"JSON Players", "생성 이력"})
        self.assertEqual(before, (self.root / "Config/DefaultGame.ini").read_bytes())

    def test_registration_preview_preserves_project_config_without_writing(self):
        path = self.root / "Config/DefaultGame.ini"
        before = path.read_bytes()
        plan = build_registration_plan(build_plan(self.project, self.tables))
        content = next(w.content for w in plan.writes if w.path == path)
        self.assertTrue(content.startswith(before))
        self.assertIn(b"Players=/Game/DataTables/DT_Players.DT_Players", content)
        self.assertIn(b"Items=/Game/DataTables/DT_Items.DT_Items", content)
        self.assertEqual(before, path.read_bytes())
        with self.assertRaisesRegex(ToolError, "찾지 못"):
            commit_registration(plan, [j["asset_path"] for j in plan.asset_jobs])
        self.assertEqual(before, path.read_bytes())

    def test_consumer_is_separate_from_generated_subsystem(self):
        source = (self.root / "Source/TableDeskSample/Private/TableDeskSampleGameMode.cpp").read_text()
        self.assertIn('#include "Data/TDSStructTypes.h"', source)
        for expression in ("GetPlayersTable()", "GetItemsTable()", "FindRow<FTDSPlayersRow>", "FindRow<FTDSItemsRow>"):
            self.assertIn(expression, source)
        config = (self.root / "Config/DefaultEngine.ini").read_text()
        self.assertIn("GlobalDefaultGameMode=/Script/TableDeskSample.TableDeskSampleGameMode", config)
        self.assertIn("EditorStartupMap=/Engine/Maps/Entry", config)
        # C++ headers use Unreal reflection's required last include convention.
        for header in (self.root / "Source").rglob("*.h"):
            includes = [line for line in header.read_text().splitlines() if line.startswith("#include")]
            self.assertTrue(includes[-1].endswith('.generated.h"'), header.name)

    def test_exe_bundle_includes_only_workbook_not_engine_project(self):
        batch = (ROOT / "build_windows.bat").read_text()
        self.assertIn('--add-data "Samples/TableDeskSample/Excel:Samples/TableDeskSample/Excel"', batch)
        self.assertNotIn('--add-data "Samples:Samples"', batch)
        self.assertFalse((ROOT / "examples").exists())

    def test_single_workbook_and_only_two_markdown_documents(self):
        self.assertEqual(sorted(p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*.xlsx")
                                if ".git" not in p.parts),
                         ["Samples/TableDeskSample/Excel/TableTemplate.xlsx"])
        self.assertEqual(sorted(p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*.md")
                                if ".git" not in p.parts), ["AGENTS.md", "README.md"])


if __name__ == "__main__":
    unittest.main()
