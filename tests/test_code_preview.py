"""Whole-project versus selected-conversion preview regression tests."""
import copy
from dataclasses import FrozenInstanceError
from pathlib import Path
import tempfile
import unittest

from test_core import fixture, SAMPLE
from tabledesk.core import Field, Issue, ToolError, build_plan, execute_plan, load_tables
from tabledesk.code_preview import build_project_code_preview, code_preview_from_plan


class WholeCodePreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = fixture(Path(self.temp.name) / 'Project')
        self.tables, issues = load_tables([SAMPLE])
        self.assertFalse(issues)

    def tearDown(self):
        self.temp.cleanup()

    def snapshot(self):
        return {p.relative_to(self.project.root).as_posix():
                (p.read_bytes(), p.stat().st_mtime_ns) if p.is_file() else None
                for p in self.project.root.rglob('*')}

    def texts(self, preview):
        return {d.filename: d.text for d in preview.documents}

    def table(self, name):
        return next(t for t in self.tables if t.name == name)

    def generate(self, tables=None):
        plan = build_plan(self.project, self.tables if tables is None else tables)
        execute_plan(plan)
        return plan

    def test_three_actual_files_not_per_table_snippets(self):
        result = build_project_code_preview(self.project, self.tables)
        self.assertEqual([d.filename for d in result.documents],
                         ['OBStructTypes.h', 'DataTableSubsystem.h', 'DataTableSubsystem.cpp'])
        self.assertEqual(result.included_tables, ('Items', 'Players'))
        text = self.texts(result)
        self.assertIn('#pragma once', text['OBStructTypes.h'])
        self.assertIn('#include "OBStructTypes.generated.h"', text['OBStructTypes.h'])
        for name in ('Items', 'Players'):
            self.assertIn(f'FOB{name}Row : public FTableRowBase', text['OBStructTypes.h'])
            self.assertIn(f'Get{name}Table() const', text['DataTableSubsystem.h'])
            self.assertIn(f'{name}Table = LoadRegisteredTable', text['DataTableSubsystem.cpp'])
        self.assertTrue(text['DataTableSubsystem.cpp'].endswith('}\n'))

    def test_preview_bytes_equal_real_conversion_output(self):
        preview = build_project_code_preview(self.project, self.tables)
        self.generate()
        for doc in preview.documents:
            self.assertEqual(doc.text, (self.project.root / doc.relative_path).read_bytes().decode('utf-8-sig'))

    def test_preview_equals_v021_expected_cpp(self):
        # UI-only revision must not silently change Unreal APIs or generator output.
        preview = build_project_code_preview(self.project, self.tables)
        expected = SAMPLE.parent / 'expected'
        for doc in preview.documents:
            self.assertEqual(doc.text, (expected / doc.filename).read_text(encoding='utf-8'))

    def test_fresh_preview_has_no_filesystem_side_effects(self):
        before = self.snapshot()
        for _ in range(2):
            build_project_code_preview(self.project, self.tables)
        self.assertEqual(before, self.snapshot())

    def test_existing_preview_does_not_write_or_touch_mtimes(self):
        self.generate()
        before = self.snapshot()
        build_project_code_preview(self.project, self.tables)
        build_project_code_preview(self.project, [])
        self.assertEqual(before, self.snapshot())

    def test_existing_unloaded_tables_are_retained(self):
        self.generate()
        result = build_project_code_preview(self.project, [self.table('Players')])
        self.assertEqual(result.incoming_tables, ('Players',))
        self.assertEqual(result.retained_tables, ('Items',))
        self.assertIn('GetItemsTable()', self.texts(result)['DataTableSubsystem.h'])

    def test_new_table_preview_includes_all_existing_tables(self):
        self.generate()
        new = copy.deepcopy(self.table('Players'))
        new.name = 'Weapons'
        result = build_project_code_preview(self.project, [new])
        self.assertEqual(result.included_tables, ('Items', 'Players', 'Weapons'))
        self.assertEqual(result.retained_tables, ('Items', 'Players'))
        self.assertFalse((self.project.root / 'DataTable/Weapons.json').exists())

    def test_no_excel_still_shows_existing_full_code(self):
        self.generate()
        result = build_project_code_preview(self.project, [])
        self.assertEqual(result.incoming_tables, ())
        self.assertEqual(result.retained_tables, ('Items', 'Players'))
        for doc in result.documents:
            self.assertEqual(doc.text, (self.project.root / doc.relative_path).read_text())

    def test_empty_project_has_empty_display_without_writes(self):
        before = self.snapshot()
        result = build_project_code_preview(self.project, [])
        self.assertEqual(result.documents, ())
        self.assertEqual(result.included_tables, ())
        self.assertEqual(before, self.snapshot())

    def test_empty_conversion_still_blocked(self):
        self.generate()
        with self.assertRaisesRegex(ToolError, '하나 이상'):
            build_plan(self.project, [])

    def test_invalid_new_table_is_explicitly_excluded(self):
        broken = self.table('Items')
        broken.issues.append(Issue('오류', broken.source, broken.sheet, 'C4', 'Invalid cell'))
        result = build_project_code_preview(self.project, self.tables)
        self.assertEqual(result.excluded_tables, ('Items',))
        self.assertEqual(result.included_tables, ('Players',))
        self.assertNotIn('FOBItemsRow', self.texts(result)['OBStructTypes.h'])

    def test_invalid_existing_schema_keeps_last_generated_version(self):
        self.generate()
        broken = self.table('Items')
        broken.fields.append(Field('BrokenNewColumn', 'Int'))
        broken.issues.append(Issue('오류', broken.source, broken.sheet, 'C4', 'Invalid cell'))
        result = build_project_code_preview(self.project, self.tables)
        self.assertEqual(result.excluded_tables, ('Items',))
        self.assertEqual(result.retained_tables, ('Items',))
        self.assertNotIn('BrokenNewColumn', self.texts(result)['OBStructTypes.h'])

    def test_all_invalid_fresh_project_is_empty_not_valid_looking_code(self):
        for t in self.tables:
            t.issues.append(Issue('오류', t.source, t.sheet, 'A1', 'Invalid'))
        result = build_project_code_preview(self.project, self.tables)
        self.assertEqual(result.documents, ())
        self.assertEqual(result.excluded_tables, ('Items', 'Players'))

    def test_selected_confirmation_is_not_all_incoming_scope(self):
        whole = build_project_code_preview(self.project, self.tables)
        selected = code_preview_from_plan(build_plan(self.project, [self.table('Players')]))
        self.assertEqual(whole.included_tables, ('Items', 'Players'))
        self.assertEqual(selected.included_tables, ('Players',))
        self.assertNotIn('GetItemsTable', self.texts(selected)['DataTableSubsystem.h'])

    def test_selected_confirmation_still_includes_retained_tables(self):
        self.generate()
        selected = code_preview_from_plan(build_plan(self.project, [self.table('Players')]))
        self.assertEqual(selected.included_tables, ('Items', 'Players'))
        self.assertEqual(selected.retained_tables, ('Items',))

    def test_value_changes_do_not_change_code_preview(self):
        before = build_project_code_preview(self.project, self.tables)
        self.table('Players').rows[0]['ID'] = 900
        after = build_project_code_preview(self.project, self.tables)
        self.assertEqual(before.documents, after.documents)

    def test_custom_prefix_and_file_paths(self):
        self.project.prefix = 'TT'
        self.project.header_subdir = 'Custom/Rows'
        result = build_project_code_preview(self.project, self.tables)
        self.assertEqual(result.documents[0].filename, 'TTStructTypes.h')
        self.assertIn('/Public/Custom/Rows/', result.documents[0].relative_path)
        self.assertIn('/Private/Custom/Rows/', result.documents[2].relative_path)
        self.assertIn('FTTPlayersRow', result.documents[0].text)

    def test_external_code_edits_block_preview_without_overwriting(self):
        self.generate()
        path = self.project.root / self.project.subsystem_header_relative
        path.write_bytes(path.read_bytes() + b'\n// externally modified\n')
        before = self.snapshot()
        with self.assertRaisesRegex(ToolError, '서브시스템'):
            build_project_code_preview(self.project, self.tables)
        self.assertEqual(before, self.snapshot())

    def test_changed_excel_blocks_stale_preview(self):
        source = Path(self.temp.name) / 'Changed.xlsx'
        source.write_bytes(SAMPLE.read_bytes())
        tables, _ = load_tables([source])
        source.write_bytes(source.read_bytes() + b'changed')
        before = self.snapshot()
        with self.assertRaisesRegex(ToolError, '엑셀이 변경'):
            build_project_code_preview(self.project, tables)
        self.assertEqual(before, self.snapshot())

    def test_preview_document_is_display_only_immutable_data(self):
        result = build_project_code_preview(self.project, self.tables)
        self.assertFalse(hasattr(result, 'writes'))
        with self.assertRaises(FrozenInstanceError):
            result.documents[0].text = 'other'


if __name__ == '__main__':
    unittest.main()
