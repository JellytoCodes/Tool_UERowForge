from __future__ import annotations
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tabledesk.core import (Field, MARKER, Project, Registry, Table, ToolError, build_plan,
    cell_name, execute_plan, header_blocks, inside, load_tables, merge_header, parse_sheet,
    register_project, relative_dir, scoped)
from tabledesk.xlsx_reader import Sheet, SpecialCell, WorkbookError, read_xlsx

SAMPLE = Path(__file__).resolve().parents[1] / "resources" / "TableTemplate.xlsx"


def fixture(root: Path) -> Project:
    root.mkdir(parents=True, exist_ok=True)
    source = root / "Source" / "OperationBreakpoint"
    source.mkdir(parents=True)
    (source / "OperationBreakpoint.Build.cs").write_text("// fixture\n")
    up = root / "OperationBreakpoint.uproject"
    up.write_text(json.dumps({"FileVersion": 3, "Modules": [{"Name": "OperationBreakpoint", "Type": "Runtime"}]}))
    return register_project(up)


def simple_sheet():
    sheet = Sheet("Players")
    values = [["TableName", "Players"], ["RowName", "RawName", "Name", "ID", "Speed", "bEnabled"],
              ["RowKey", "String", "Name", "Int", "Float", "Bool"],
              ["Player_001", "기본 플레이어", "DefaultPlayer", 1, 1.5, True]]
    for r, row in enumerate(values, 1):
        for c, value in enumerate(row, 1):
            sheet.cells[r, c] = value
    return sheet


class SchemaTests(unittest.TestCase):
    def parse(self, sheet=None):
        return parse_sheet(sheet or simple_sheet(), Path("fixture.xlsx"))

    def test_valid_template_shape(self):
        table = self.parse()
        self.assertTrue(table.valid)
        self.assertEqual(table.rows[0]["Name"], "DefaultPlayer")
        self.assertEqual(table.rows[0]["RowName"], "Player_001")

    def test_duplicate_keys_case_insensitive(self):
        sh = simple_sheet()
        for c in range(1, 7):
            sh.cells[5, c] = sh.get(4, c)
        sh.cells[5, 1] = "player_001"
        self.assertFalse(self.parse(sh).valid)

    def test_reserved_empty_rowname(self):
        for key in ("None", "none", "", "with space", "../escape", 123):
            sh = simple_sheet()
            sh.cells[4, 1] = key
            with self.subTest(key=key):
                self.assertFalse(self.parse(sh).valid)

    def test_int32_boundaries(self):
        for value, valid in [(-2147483648, True), (2147483647, True), (2147483648, False), (1.2, False), (True, False)]:
            sh = simple_sheet()
            sh.cells[4, 4] = value
            self.assertEqual(self.parse(sh).valid, valid)

    def test_integer_strings(self):
        sh = simple_sheet()
        sh.cells[4, 4] = "42"
        self.assertEqual(self.parse(sh).rows[0]["ID"], 42)

    def test_float_finite_and_range(self):
        for value in ("NaN", "Infinity", "-Infinity", "1e39", "abc"):
            sh = simple_sheet()
            sh.cells[4, 5] = value
            self.assertFalse(self.parse(sh).valid)

    def test_bool_values(self):
        for value, expected in [(True, True), (False, False), (1, True), (0, False), ("TRUE", True), ("false", False)]:
            sh = simple_sheet()
            sh.cells[4, 6] = value
            self.assertEqual(self.parse(sh).rows[0]["bEnabled"], expected)

    def test_invalid_bool_and_missing_numeric(self):
        for col, value in [(6, "maybe"), (4, None), (5, ""), (6, None)]:
            sh = simple_sheet()
            sh.cells[4, col] = value
            self.assertFalse(self.parse(sh).valid)

    def test_string_requires_text_to_preserve_zeros(self):
        sh = simple_sheet()
        sh.cells[4, 2] = 100
        self.assertFalse(self.parse(sh).valid)
        sh.cells[4, 2] = "00100"
        self.assertEqual(self.parse(sh).rows[0]["RawName"], "00100")

    def test_empty_string_and_name(self):
        sh = simple_sheet()
        sh.cells[4, 2] = None
        sh.cells[4, 3] = None
        table = self.parse(sh)
        self.assertTrue(table.valid)
        self.assertEqual(table.rows[0]["RawName"], "")
        self.assertEqual(table.rows[0]["Name"], "None")

    def test_formula_error_and_date_rejected(self):
        for kind in ("수식", "Excel 오류", "날짜/시간"):
            sh = simple_sheet()
            sh.cells[4, 4] = SpecialCell(kind, "123")
            self.assertFalse(self.parse(sh).valid)

    def test_duplicate_fields_and_cpp_injection(self):
        for name in ("name", "class", "StaticStruct", 'X; system("test")', "1HP", "한글"):
            sh = simple_sheet()
            sh.cells[2, 4] = name
            self.assertFalse(self.parse(sh).valid)

    def test_unsupported_type_and_multiple_keys(self):
        for typ in ("TArray<int32>", "RowKey", "Text", "UObject*", ""):
            sh = simple_sheet()
            sh.cells[3, 4] = typ
            self.assertFalse(self.parse(sh).valid)

    def test_only_row_key_rejected(self):
        sh = Sheet("Players", {(1, 1): "TableName", (1, 2): "Players", (2, 1): "RowName", (3, 1): "RowKey", (4, 1): "P1"})
        self.assertFalse(self.parse(sh).valid)

    def test_merged_and_blank_table_rejected(self):
        sh = simple_sheet()
        sh.merged = ["A1:B1"]
        self.assertFalse(self.parse(sh).valid)
        sh = simple_sheet()
        sh.cells = {k: v for k, v in sh.cells.items() if k[0] < 4}
        self.assertFalse(self.parse(sh).valid)

    def test_extra_cell_and_missing_field(self):
        sh = simple_sheet()
        sh.cells[4, 9] = "lost value"
        self.assertFalse(self.parse(sh).valid)
        sh = simple_sheet()
        sh.cells[2, 4] = None
        self.assertFalse(self.parse(sh).valid)

    def test_subpath_rejected(self):
        sh = simple_sheet()
        sh.cells[1, 4], sh.cells[1, 5] = "SubPath", "../Other"
        self.assertFalse(self.parse(sh).valid)

    def test_coordinate(self):
        self.assertEqual(cell_name(27, 9), "AA9")


class XlsxTests(unittest.TestCase):
    def test_real_xlsx_reader(self):
        sheets = read_xlsx(SAMPLE)
        self.assertEqual([s.name for s in sheets], ["Players", "Items"])
        self.assertEqual(sheets[0].get(4, 2), "기본 플레이어")
        self.assertIs(sheets[0].get(4, 7), True)
        tables, issues = load_tables([SAMPLE])
        self.assertFalse(issues)
        self.assertTrue(all(t.valid for t in tables))
        self.assertEqual(sum(len(t.rows) for t in tables), 6)

    def test_missing_file_reported(self):
        tables, issues = load_tables([Path("does-not-exist.xlsx")])
        self.assertFalse(tables)
        self.assertEqual(len(issues), 1)

    def test_duplicate_tables_across_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            other = Path(tmp) / "another.xlsx"
            other.write_bytes(SAMPLE.read_bytes())
            tables, issues = load_tables([SAMPLE, other])
            self.assertTrue(all(not t.valid for t in tables))

    def test_unsupported_file(self):
        with self.assertRaises(WorkbookError):
            read_xlsx(Path("foo.xls"))

    def test_corrupt_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "bad.xlsx"
            p.write_bytes(b"not a zip archive")
            with self.assertRaises(WorkbookError):
                read_xlsx(p)


class PathTests(unittest.TestCase):
    def test_windows_and_parent_escape(self):
        for bad in ("../escape", "a/../../escape", "C:/temp", "C:relative", r"\\server\share", "/tmp", ".", "a/./b", "a//b", "CON", "a/NUL.json", "a. ", "a/*"):
            with self.subTest(bad=bad), self.assertRaises(ToolError):
                relative_dir(bad)

    def test_normalize_windows_relative(self):
        self.assertEqual(relative_dir(r"Data\Tables\Players"), "Data/Tables/Players")

    def test_symlink_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "Project"
            root.mkdir()
            try:
                (root / "link").symlink_to(Path(tmp), target_is_directory=True)
            except OSError:
                self.skipTest("Symlinks require platform permissions")
            with self.assertRaises(ToolError):
                inside(root, "link/escape.json")

    def test_symlink_outside_narrow_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Base").mkdir()
            (root / "Other").mkdir()
            try:
                (root / "Base" / "link").symlink_to(root / "Other", target_is_directory=True)
            except OSError:
                self.skipTest("Symlinks require platform permissions")
            with self.assertRaises(ToolError):
                scoped(root, "Base", "link/file.json")


class ConversionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "Project"
        self.project = fixture(self.root)
        self.tables, self.issues = load_tables([SAMPLE])

    def tearDown(self):
        self.temp.cleanup()

    def test_first_generation(self):
        plan = build_plan(self.project, self.tables)
        self.assertTrue(plan.header_changed)
        self.assertEqual(len(plan.writes), 6)
        self.assertEqual(plan.asset_jobs[0]["struct_path"], "/Script/OperationBreakpoint.OBPlayersRow")
        backup = execute_plan(plan)
        self.assertTrue(backup.is_dir())
        text = (self.root / self.project.header_relative).read_text()
        self.assertIn("FTableRowBase", text)
        self.assertIn("FOBPlayersRow", text)
        self.assertIn("OPERATIONBREAKPOINT_API", text)
        self.assertNotIn("FString RowName", text)
        self.assertIn("FName Name = NAME_None;", text)
        self.assertFalse(list(self.root.rglob("*.generated.h")))

    def test_idempotent_no_header_write(self):
        execute_plan(build_plan(self.project, self.tables))
        header = self.root / self.project.header_relative
        before = header.stat().st_mtime_ns
        plan = build_plan(self.project, self.tables)
        self.assertFalse(plan.changed)
        self.assertIsNone(execute_plan(plan))
        self.assertEqual(header.stat().st_mtime_ns, before)

    def test_values_only_preserve_header(self):
        execute_plan(build_plan(self.project, self.tables))
        self.tables[0].rows[0]["ID"] = 77
        plan = build_plan(self.project, [self.tables[0]])
        self.assertFalse(plan.header_changed)
        execute_plan(plan)
        self.assertIn("FOBItemsRow", (self.root / self.project.header_relative).read_text())

    def test_schema_change(self):
        execute_plan(build_plan(self.project, self.tables))
        t = self.tables[0]
        t.fields.append(Field("Stamina", "Int"))
        for row in t.rows:
            row["Stamina"] = 80
        plan = build_plan(self.project, [t])
        self.assertTrue(plan.header_changed)
        self.assertIn("Stamina", plan.header_diff())
        execute_plan(plan)
        self.assertIn("FOBItemsRow", (self.root / self.project.header_relative).read_text())

    def test_manual_header_not_overwritten(self):
        p = self.root / self.project.header_relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("// developer code")
        with self.assertRaises(ToolError):
            build_plan(self.project, self.tables)
        self.assertEqual(p.read_text(), "// developer code")

    def test_unowned_json_conflict(self):
        path = self.root / "DataTable/Players.json"
        path.parent.mkdir(parents=True)
        path.write_text("[]")
        with self.assertRaises(ToolError):
            build_plan(self.project, self.tables)

    def test_external_json_edit(self):
        execute_plan(build_plan(self.project, self.tables))
        path = self.root / "DataTable/Players.json"
        path.write_text("[]")
        with self.assertRaises(ToolError):
            build_plan(self.project, self.tables)

    def test_external_managed_block_edit(self):
        execute_plan(build_plan(self.project, self.tables))
        header = self.root / self.project.header_relative
        header.write_text(header.read_text().replace("int32 ID = 0", "int32 ID = 42"))
        with self.assertRaises(ToolError):
            build_plan(self.project, self.tables)

    def test_manual_code_outside_markers_preserved(self):
        execute_plan(build_plan(self.project, self.tables))
        header = self.root / self.project.header_relative
        header.write_text(header.read_text() + "\n// manually maintained note\n")
        plan = build_plan(self.project, self.tables)
        self.assertIn(b"manually maintained note", plan.writes[0].content)

    def test_plan_conflict_between_preview_and_apply(self):
        plan = build_plan(self.project, self.tables)
        header = self.root / self.project.header_relative
        header.parent.mkdir(parents=True, exist_ok=True)
        header.write_text("// changed after preview")
        with self.assertRaises(ToolError):
            execute_plan(plan)

    def test_backup_exact_and_no_unselected_removal(self):
        execute_plan(build_plan(self.project, self.tables))
        path = self.root / "DataTable/Players.json"
        before = path.read_bytes()
        self.tables[0].rows[0]["ID"] = 9
        backup = execute_plan(build_plan(self.project, [self.tables[0]]))
        self.assertEqual((backup / path.relative_to(self.root)).read_bytes(), before)
        self.assertTrue((self.root / "DataTable/Items.json").is_file())

    def test_rollback_on_write_failure(self):
        from tabledesk import core
        plan = build_plan(self.project, self.tables)
        real_write = core.atomic_write
        count = 0
        def failing(path, data):
            nonlocal count
            if path in {w.path for w in plan.writes}:
                count += 1
                if count == 2:
                    raise OSError("simulated disk error")
            return real_write(path, data)
        with mock.patch("tabledesk.core.atomic_write", side_effect=failing):
            with self.assertRaises(ToolError):
                execute_plan(plan)
        self.assertFalse((self.root / self.project.header_relative).exists())

    def test_route_override(self):
        self.project.routes["Players"] = "New/Sub"
        plan = build_plan(self.project, [self.tables[0]])
        self.assertEqual(plan.asset_jobs[0]["asset_path"], "/Game/DataTables/New/Sub/DT_Players")
        self.assertIn("New/Sub", str(plan.writes[1].path))

    def test_invalid_project_no_module(self):
        self.project.module = "Missing"
        with self.assertRaises(ToolError):
            build_plan(self.project, self.tables)

    def test_damaged_markers(self):
        execute_plan(build_plan(self.project, self.tables))
        header = self.root / self.project.header_relative
        header.write_text(header.read_text().replace("// END TABLEDESK: Players", "// broken"))
        with self.assertRaises(ToolError):
            build_plan(self.project, self.tables)

    def test_removed_field_warning(self):
        execute_plan(build_plan(self.project, self.tables))
        table = self.tables[0]
        table.fields = [f for f in table.fields if f.name != "MaxHP"]
        for row in table.rows:
            del row["MaxHP"]
        plan = build_plan(self.project, [table])
        self.assertTrue(any("삭제 필드=['MaxHP']" in n for n in plan.notes))


class RegistryTests(unittest.TestCase):
    def test_register_persist_remove_without_deleting_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            p = fixture(Path(tmp) / "project")
            r = Registry(home)
            r.add(p)
            self.assertEqual(r.projects[0].prefix, "OB")
            r2 = Registry(home)
            self.assertEqual(r2.projects[0].name, p.name)
            r2.remove(p.id)
            self.assertTrue(Path(p.uproject).exists())
            self.assertFalse(Registry(home).projects)

    def test_duplicate_registration(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = fixture(Path(tmp) / "project")
            registry = Registry(Path(tmp) / "home")
            registry.add(p)
            registry.add(register_project(Path(p.uproject)))
            self.assertEqual(len(registry.projects), 1)

    def test_registry_concurrent_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = Registry(Path(tmp))
            b = Registry(Path(tmp))
            a.save()
            with self.assertRaises(ToolError):
                b.save()


if __name__ == "__main__":
    unittest.main()

class AdditionalIntegrityTests(unittest.TestCase):
    def test_excel_change_before_plan_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sample = root / 'source.xlsx'
            sample.write_bytes(SAMPLE.read_bytes())
            project = fixture(root / 'Project')
            tables, _ = load_tables([sample])
            sample.write_bytes(sample.read_bytes() + b'changed')
            with self.assertRaises(ToolError):
                build_plan(project, tables)

    def test_excel_change_after_preview_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sample = root / 'source.xlsx'
            sample.write_bytes(SAMPLE.read_bytes())
            project = fixture(root / 'Project')
            tables, _ = load_tables([sample])
            plan = build_plan(project, tables)
            sample.write_bytes(sample.read_bytes() + b'changed')
            with self.assertRaises(ToolError):
                execute_plan(plan)
            self.assertFalse((project.root / project.header_relative).exists())

    def test_ooxml_escaped_literal_and_emoji(self):
        from tabledesk.xlsx_reader import _xml, _text
        text = _xml(b'<si xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><t>_x005F_x0041_ _xD83D__xDE00_</t></si>')
        self.assertEqual(_text(text), '_x0041_ \U0001f600')

    def test_phonetic_guide_not_in_string(self):
        from tabledesk.xlsx_reader import _xml, _text
        text = _xml('<si xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><r><t>東京</t></r><rPh sb="0" eb="2"><t>とうきょう</t></rPh></si>'.encode())
        self.assertEqual(_text(text), '東京')

    def test_xml_entities_rejected(self):
        from tabledesk.xlsx_reader import _xml
        with self.assertRaises(WorkbookError):
            _xml(b'<!DOCTYPE a [<!ENTITY b "value">]><a>&b;</a>')

class DuplicateHeaderTests(unittest.TestCase):
    def test_other_folder_same_basename_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = fixture(Path(tmp) / 'Project')
            (project.root / 'Source/OperationBreakpoint/OBStructTypes.h').write_text('// manual header')
            tables, _ = load_tables([SAMPLE])
            with self.assertRaises(ToolError):
                build_plan(project, tables)
