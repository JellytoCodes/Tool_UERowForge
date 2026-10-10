"""Regression coverage for the flat output defaults introduced in v0.1.1."""
from dataclasses import asdict
import json
from pathlib import Path
import tempfile
import unittest

from test_core import SAMPLE, fixture, simple_sheet
from tabledesk.core import (Registry, ToolError, build_plan, execute_plan,
                            load_tables, parse_sheet)


class DefaultPathTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project = fixture(self.root / "Project")
        self.tables, issues = load_tables([SAMPLE])
        self.assertFalse(issues)

    def tearDown(self):
        self.temp.cleanup()

    def test_new_project_has_short_default_paths(self):
        self.assertEqual(self.project.header_subdir, "Data")
        self.assertEqual(self.project.json_subdir, "DataTable")
        self.assertEqual(self.project.header_relative,
                         "Source/OperationBreakpoint/Public/Data/OBStructTypes.h")
        # No requested change to the Unreal Content default.
        self.assertEqual(self.project.asset_subdir, "DataTables")

    def test_shipped_template_has_no_implicit_subfolders(self):
        self.assertEqual([table.name for table in self.tables], ["Players", "Items"])
        self.assertEqual([table.subpath for table in self.tables], ["", ""])
        self.assertEqual([self.project.route_for(table) for table in self.tables], ["", ""])

    def test_flat_files_are_written_without_table_named_folders(self):
        plan = build_plan(self.project, self.tables)
        expected = {
            "Source/OperationBreakpoint/Public/Data/OBStructTypes.h",
            "Source/OperationBreakpoint/Public/Data/.tabledesk-manifest.json",
            "DataTable/Players.json", "DataTable/Items.json",
            "Source/OperationBreakpoint/Public/Data/DataTableSubsystem.h",
            "Source/OperationBreakpoint/Private/Data/DataTableSubsystem.cpp",
        }
        self.assertEqual({write.path.relative_to(self.project.root).as_posix()
                          for write in plan.writes}, expected)
        execute_plan(plan)
        self.assertEqual({p.name for p in (self.project.root / "DataTable").iterdir()},
                         {"Players.json", "Items.json"})
        self.assertFalse((self.project.root / "DataSource").exists())
        self.assertFalse((self.project.root / "Source/OperationBreakpoint/Public/Data/Generated").exists())
        self.assertFalse(list(self.project.root.rglob("*.uasset")))
        self.assertEqual(plan.asset_jobs[0]["asset_path"], "/Game/DataTables/DT_Players")
        self.assertFalse(build_plan(self.project, self.tables).changed)

    def test_missing_blank_or_whitespace_subpath_means_no_extra_path(self):
        for value in (None, "", "  "):
            with self.subTest(value=value):
                sheet = simple_sheet()
                sheet.cells[1, 4] = "SubPath"
                sheet.cells[1, 5] = value
                table = parse_sheet(sheet, Path("fixture.xlsx"))
                self.assertTrue(table.valid)
                self.assertEqual(self.project.route_for(table), "")

    def test_user_excel_subpath_is_still_respected(self):
        sheet = simple_sheet()
        sheet.cells[1, 4], sheet.cells[1, 5] = "SubPath", "Characters\\Playable"
        table = parse_sheet(sheet, Path("fixture.xlsx"))
        self.assertTrue(table.valid)
        plan = build_plan(self.project, [table])
        self.assertEqual(plan.writes[1].path,
                         self.project.root / "DataTable/Characters/Playable/Players.json")

    def test_explicit_empty_override_survives_restart_and_beats_old_template(self):
        self.tables[0].subpath = "Characters"
        self.project.routes["Players"] = ""
        registry = Registry(self.root / "Settings")
        registry.add(self.project)
        restored = Registry(registry.home).projects[0]
        self.assertIn("Players", restored.routes)
        self.assertEqual(restored.route_for(self.tables[0]), "")
        self.assertEqual(build_plan(restored, [self.tables[0]]).writes[1].path,
                         self.project.root / "DataTable/Players.json")

    def test_custom_settings_are_not_overwritten_when_app_is_updated(self):
        self.project.header_subdir = "Types/Rows"
        self.project.json_subdir = "Exports/Tables"
        self.project.asset_subdir = "GameData"
        self.project.routes = {"Players": "Characters"}
        registry = Registry(self.root / "Settings")
        registry.add(self.project)
        restored = Registry(registry.home).projects[0]
        self.assertEqual(asdict(restored), asdict(self.project))

    def test_saved_legacy_defaults_are_preserved_until_explicit_reset(self):
        self.project.header_subdir = "Data/Generated"
        self.project.json_subdir = "DataSource/DataTables"
        registry = Registry(self.root / "Settings")
        registry.add(self.project)
        restored = Registry(registry.home).projects[0]
        self.assertEqual(restored.header_subdir, "Data/Generated")
        self.assertEqual(restored.json_subdir, "DataSource/DataTables")

    def test_registry_missing_optional_paths_gets_new_defaults(self):
        record = asdict(self.project)
        for key in ("header_subdir", "json_subdir", "routes"):
            record.pop(key)
        home = self.root / "Settings"
        home.mkdir()
        (home / "projects.json").write_text(json.dumps({"version": 1, "projects": [record]}))
        restored = Registry(home).projects[0]
        self.assertEqual(restored.header_subdir, "Data")
        self.assertEqual(restored.json_subdir, "DataTable")
        self.assertEqual(restored.routes, {})

    def test_reset_does_not_silently_duplicate_a_previously_generated_header(self):
        self.project.header_subdir = "Data/Generated"
        execute_plan(build_plan(self.project, self.tables))
        legacy_header = self.project.root / self.project.header_relative
        before = legacy_header.read_bytes()
        self.project.header_subdir = "Data"
        with self.assertRaisesRegex(ToolError, "같은 이름의 헤더"):
            build_plan(self.project, self.tables)
        self.assertEqual(legacy_header.read_bytes(), before)
        self.assertFalse((self.project.root / self.project.header_relative).exists())


if __name__ == "__main__":
    unittest.main()
