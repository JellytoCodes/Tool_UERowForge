"""Workbook layout and generated enum regression tests; no private workbook dependency."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from test_core import fixture, simple_sheet
from uerowforge.core import build_plan, cell_name, execute_plan, load_tables, parse_sheet, ToolError
from uerowforge.xlsx_reader import Sheet, read_xlsx


def script_sheet(name="Training", enum_type="Enum"):
    values = [
        ["번호", "UI 위치", "표시 문구", "음성", "이전 행", "열림", "메모"],
        ["ID", "Layer", "Script", "Sound", "Prev_ID", "UI Open", "Note"],
        ["Int", enum_type, "Text", "SoftObject", "Int", "Bool", "String(Edit only)"],
        [1, "Main", "첫 줄\n둘째 줄", None, None, None, "내보내지 않는 메모"],
        [2, "Sub", "두 번째", "/Game/Audio/Voice.Voice", 1, True, "기획 메모"],
    ]
    return Sheet(name, {(r, c): value for r, row in enumerate(values, 1)
                        for c, value in enumerate(row, 1) if value is not None})


def write_workbook(path, sheets):
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    workbook = ET.Element("workbook", xmlns=ns)
    descriptors = ET.SubElement(workbook, "sheets")
    relationships = ET.Element("Relationships", xmlns="http://schemas.openxmlformats.org/package/2006/relationships")
    with ZipFile(path, "w") as archive:
        for index, sheet in enumerate(sheets, 1):
            ET.SubElement(descriptors, "sheet", name=sheet.name, sheetId=str(index), **{f"{{{rel}}}id": f"rId{index}"})
            ET.SubElement(relationships, "Relationship", Id=f"rId{index}", Type=rel + "/worksheet", Target=f"worksheets/sheet{index}.xml")
            xml = ET.Element("worksheet", xmlns=ns)
            data = ET.SubElement(xml, "sheetData")
            for row in sorted({r for r, c in sheet.cells}):
                item = ET.SubElement(data, "row", r=str(row))
                for (r, col), value in sorted(sheet.cells.items()):
                    if r != row:
                        continue
                    cell = ET.SubElement(item, "c", r=cell_name(col, r))
                    if isinstance(value, str):
                        cell.set("t", "inlineStr")
                        ET.SubElement(ET.SubElement(cell, "is"), "t").text = value
                    else:
                        cell.set("t", "b" if isinstance(value, bool) else "n")
                        ET.SubElement(cell, "v").text = str(int(value)) if isinstance(value, bool) else str(value)
            archive.writestr(f"xl/worksheets/sheet{index}.xml", ET.tostring(xml))
        archive.writestr("xl/workbook.xml", ET.tostring(workbook))
        archive.writestr("xl/_rels/workbook.xml.rels", ET.tostring(relationships))


class LayoutTests(unittest.TestCase):
    def test_first_physical_sheet_is_skipped_regardless_of_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.xlsx"
            write_workbook(path, [simple_sheet(), Sheet("_OtherGuide", {(1, 1): "참고"}), script_sheet()])
            self.assertEqual([s.name for s in read_xlsx(path)], ["Training"])
            tables, issues = load_tables([path])
            self.assertFalse(issues)
            self.assertEqual(len(tables), 1)
            self.assertTrue(tables[0].valid, tables[0].issues)

    def test_description_header_id_key_and_blank_defaults(self):
        table = parse_sheet(script_sheet(), Path("input.xlsx"))
        self.assertTrue(table.valid, table.issues)
        self.assertEqual(table.rows[0]["RowName"], "1")
        self.assertEqual(table.rows[0]["ID"], 1)
        self.assertEqual(table.rows[0]["Prev_ID"], 0)
        self.assertIs(table.rows[0]["UI_Open"], False)
        self.assertEqual(table.rows[0]["Sound"], "None")
        self.assertEqual(table.rows[0]["Script"], "첫 줄\n둘째 줄")
        self.assertNotIn("Note", table.rows[0])
        self.assertNotIn("Note", [f.name for f in table.fields])

    def test_field_names_in_first_row_also_supported(self):
        sheet = script_sheet()
        for col in range(1, 8):
            sheet.cells[1, col], sheet.cells[2, col] = sheet.get(2, col), sheet.get(1, col)
        self.assertTrue(parse_sheet(sheet, Path("input.xlsx")).valid)

    def test_missing_types_reported_once_without_guessing_from_guide(self):
        sheet = script_sheet()
        sheet.cells = {key: value for key, value in sheet.cells.items() if key[0] != 3}
        table = parse_sheet(sheet, Path("input.xlsx"))
        self.assertEqual(len(table.issues), 1)
        self.assertIn("타입 행", table.issues[0].message)

    def test_numeric_key_duplicate_and_invalid_id_rejected(self):
        for value in (1, None, "not_an_int", 1.2):
            sheet = script_sheet()
            sheet.cells[5, 1] = value
            self.assertFalse(parse_sheet(sheet, Path("input.xlsx")).valid)

    def test_normalized_field_name_collision_rejected(self):
        sheet = script_sheet()
        sheet.cells[2, 5] = "UI_Open"
        self.assertFalse(parse_sheet(sheet, Path("input.xlsx")).valid)

    def test_soft_object_requires_full_path(self):
        for value in ("VO_Intro", "/Game/Audio/Voice", "../Voice", 10):
            sheet = script_sheet()
            sheet.cells[5, 4] = value
            table = parse_sheet(sheet, Path("input.xlsx"))
            self.assertFalse(table.valid)
            self.assertTrue(any("전체 참조 경로" in i.message for i in table.issues))

    def test_enum_observed_members_none_and_invalid_values(self):
        sheet = script_sheet()
        for value in (0, "0", "None", None):
            sheet.cells[4, 2] = value
            table = parse_sheet(sheet, Path("input.xlsx"))
            self.assertTrue(table.valid, table.issues)
            self.assertEqual(table.rows[0]["Layer"], "None")
            self.assertEqual(table.fields[2].enum_values, ("None", "Sub"))
        for value in ("with space", "class", "한글", 1, False):
            sheet.cells[4, 2] = value
            self.assertFalse(parse_sheet(sheet, Path("input.xlsx")).valid)

    def test_editor_only_column_cannot_replace_all_runtime_fields(self):
        sheet = Sheet("Empty", {(1, 1): "TableName", (1, 2): "Empty", (2, 1): "RowName", (3, 1): "RowKey",
                                (2, 2): "Note", (3, 2): "String(Edit only)", (4, 1): "One", (4, 2): "Memo"})
        self.assertFalse(parse_sheet(sheet, Path("input.xlsx")).valid)

    def test_editor_only_header_and_values_are_not_cpp_schema(self):
        sheet = script_sheet()
        sheet.cells[2, 7] = "기획 메모"
        table = parse_sheet(sheet, Path("input.xlsx"))
        self.assertTrue(table.valid, table.issues)
        self.assertNotIn("기획_메모", [f.name for f in table.fields])


class EnumGenerationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = fixture(Path(self.temp.name) / "Project")

    def table(self, sheet=None):
        table = parse_sheet(sheet or script_sheet(), Path(self.temp.name) / "input.xlsx")
        self.assertTrue(table.valid, table.issues)
        return table

    def test_generation_reflected_enum_text_soft_path_and_no_assets(self):
        plan = build_plan(self.project, [self.table()])
        execute_plan(plan)
        header = plan.writes[0].path.read_text()
        self.assertIn("UENUM(BlueprintType)\nenum class ETrainingLayer : uint8", header)
        self.assertIn("None = 0,\n    Main = 1,\n    Sub = 2,", header)
        self.assertIn("FText Script = FText::GetEmpty();", header)
        self.assertIn("FSoftObjectPath Sound = FSoftObjectPath();", header)
        self.assertIn("ETrainingLayer Layer = ETrainingLayer::None;", header)
        self.assertNotIn(" Note ", header)
        includes = [line for line in header.splitlines() if line.startswith("#include")]
        self.assertTrue(includes[-1].endswith('StructTypes.generated.h"'))
        self.assertFalse(list(self.project.root.rglob("*.uasset")))
        self.assertFalse((self.project.root / "Config/DefaultGame.ini").exists())
        self.assertFalse(build_plan(self.project, [self.table()]).changed)

    def test_enum_values_only_change_keeps_cpp_and_paths(self):
        execute_plan(build_plan(self.project, [self.table()]))
        sheet = script_sheet()
        sheet.cells[4, 2], sheet.cells[5, 2] = "Sub", "Main"
        plan = build_plan(self.project, [self.table(sheet)])
        self.assertEqual({w.label for w in plan.changed}, {"JSON Training", "생성 이력"})

    def test_reordering_removing_and_adding_values_keeps_existing_numbers(self):
        execute_plan(build_plan(self.project, [self.table()]))
        sheet = script_sheet()
        sheet.cells[4, 2], sheet.cells[5, 2] = "Sub", "HUD"
        plan = build_plan(self.project, [self.table(sheet)])
        execute_plan(plan)
        header = plan.writes[0].path.read_text()
        self.assertIn("None = 0,\n    Main = 1,\n    Sub = 2,\n    HUD = 3,", header)

    def test_named_shared_enum_unions_selected_and_preserves_unselected_json(self):
        first = self.table(script_sheet("First", "Enum:ESharedLayer"))
        second_sheet = script_sheet("Second", "Enum:ESharedLayer")
        second_sheet.cells[5, 2] = "HUD"
        second = self.table(second_sheet)
        execute_plan(build_plan(self.project, [first, second]))
        unselected = self.project.root / "DataTable/First.json"
        before = unselected.read_bytes(), unselected.stat().st_mtime_ns
        second_sheet.cells[5, 2] = "NewValue"
        plan = build_plan(self.project, [self.table(second_sheet)])
        execute_plan(plan)
        header = plan.writes[0].path.read_text()
        self.assertEqual(header.count("enum class ESharedLayer : uint8"), 1)
        self.assertIn("HUD = 3,\n    NewValue = 4,", header)
        self.assertEqual(before, (unselected.read_bytes(), unselected.stat().st_mtime_ns))
        self.assertFalse(build_plan(self.project, [self.table(second_sheet)]).changed)

    def test_managed_enum_external_edit_and_corrupt_history_are_blocked(self):
        plan = build_plan(self.project, [self.table()])
        execute_plan(plan)
        header = plan.writes[0].path
        original = header.read_bytes()
        header.write_bytes(original.replace(b"Main = 1", b"Main = 7"))
        with self.assertRaisesRegex(ToolError, "Enum"):
            build_plan(self.project, [self.table()])
        header.write_bytes(original)
        state = json.loads(plan.manifest_path.read_bytes())
        state["enums"]["ETrainingLayer"] = ["None", "Sub", "Main"]
        plan.manifest_path.write_text(json.dumps(state))
        with self.assertRaisesRegex(ToolError, "Enum"):
            build_plan(self.project, [self.table()])

    def test_user_enum_definition_is_not_overwritten(self):
        path = self.project.root / "Source/OperationBreakpoint/UserTypes.h"
        path.write_text("enum class ETrainingLayer : unsigned char { Existing };")
        with self.assertRaisesRegex(ToolError, "동명 Enum"):
            build_plan(self.project, [self.table()])

    def test_revision_5_migration_preserves_cpp_bytes(self):
        table = parse_sheet(simple_sheet(), Path("input.xlsx"))
        plan = build_plan(self.project, [table])
        execute_plan(plan)
        state = json.loads(plan.manifest_path.read_bytes())
        state["generator_revision"] = 5
        plan.manifest_path.write_text(json.dumps(state))
        migrated = build_plan(self.project, [table])
        self.assertEqual([w.label for w in migrated.changed], ["생성 이력"])

    def test_enum_save_failure_restores_existing_outputs(self):
        execute_plan(build_plan(self.project, [self.table()]))
        sheet = script_sheet()
        sheet.cells[5, 2] = "HUD"
        plan = build_plan(self.project, [self.table(sheet)])
        before = {w.path: w.path.read_bytes() for w in plan.writes}
        original_replace = __import__("os").replace
        failed = False
        def fail_once(source, destination):
            nonlocal failed
            if Path(destination) == plan.manifest_path and not failed:
                failed = True
                raise OSError("injected write failure")
            return original_replace(source, destination)
        with patch("uerowforge.core.os.replace", side_effect=fail_once):
            with self.assertRaises((OSError, ToolError)):
                execute_plan(plan)
        self.assertEqual(before, {w.path: w.path.read_bytes() for w in plan.writes})
