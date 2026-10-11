"""Runtime registration tests with fake saved asset bytes, not Unreal asset tests."""
import codecs
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from test_core import fixture, SAMPLE
from uerowforge.core import ToolError, build_plan, execute_plan, load_tables
from uerowforge.runtime_registration import build_registration_plan, commit_registration


class RegistrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.project=fixture(Path(self.temp.name)/"Project")
        self.tables,_=load_tables([SAMPLE])
        execute_plan(build_plan(self.project, self.tables))
        self.ini=self.project.root/"Config/DefaultGame.ini"

    def tearDown(self):
        self.temp.cleanup()

    def registration(self, tables=None):
        return build_registration_plan(build_plan(self.project, self.tables if tables is None else tables))

    def fake_saved_files(self, plan):
        for job in plan.asset_jobs:
            path=self.project.root/"Content"/(job["asset_path"][6:]+".uasset")
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(b"fixture-only; not an Unreal package")
        return [j["asset_path"] for j in plan.asset_jobs]

    def commit(self, tables=None):
        plan=self.registration(tables)
        commit_registration(plan,self.fake_saved_files(plan))
        return plan

    def test_conversion_and_registration_preview_do_not_create_ini(self):
        self.assertFalse(self.ini.exists())
        self.registration()
        self.assertFalse(self.ini.exists())

    def test_success_registers_full_object_paths(self):
        self.commit()
        text=self.ini.read_text()
        self.assertIn("[UETableDesk.DataTables]",text)
        self.assertIn("Players=/Game/DataTables/DT_Players.DT_Players",text)
        self.assertIn("Items=/Game/DataTables/DT_Items.DT_Items",text)
        self.assertFalse(build_plan(self.project,self.tables).changed)

    def test_idempotent_registration_does_not_rewrite_any_file(self):
        self.commit()
        before=self.ini.stat().st_mtime_ns
        plan=self.registration()
        self.assertFalse(plan.changed)
        self.assertIsNone(commit_registration(plan,self.fake_saved_files(plan)))
        self.assertEqual(before,self.ini.stat().st_mtime_ns)

    def test_partial_success_does_not_register_any_new_paths(self):
        plan=self.registration()
        paths=self.fake_saved_files(plan)
        with self.assertRaisesRegex(ToolError,"일부"):
            commit_registration(plan,paths[:1])
        self.assertFalse(self.ini.exists())

    def test_saved_result_without_disk_file_is_rejected(self):
        plan=self.registration()
        with self.assertRaisesRegex(ToolError,"찾지 못"):
            commit_registration(plan,[j["asset_path"] for j in plan.asset_jobs])
        self.assertFalse(self.ini.exists())

    def test_unrelated_config_comments_crlf_and_bom_preserved(self):
        self.ini.parent.mkdir()
        before=codecs.BOM_UTF8+'; 사용자 설정\r\n[/Script/EngineSettings.GeneralProjectSettings]\r\nProjectName=Project\r\n'.encode()
        self.ini.write_bytes(before)
        self.commit()
        self.assertTrue(self.ini.read_bytes().startswith(before))
        self.assertNotIn(b"\n",self.ini.read_bytes().replace(b"\r\n",b""))

    def test_utf16_config_is_preserved(self):
        self.ini.parent.mkdir()
        prefix=codecs.BOM_UTF16_LE
        before=prefix+'; 설정\r\n[Other]\r\nValue=1\r\n'.encode('utf-16-le')
        self.ini.write_bytes(before)
        self.commit()
        self.assertTrue(self.ini.read_bytes().startswith(before))
        self.assertIn('Players=',self.ini.read_bytes()[2:].decode('utf-16-le'))
        self.assertFalse(self.registration().changed)

    def test_unrelated_config_edit_between_imports_allowed(self):
        self.commit()
        self.ini.write_text(self.ini.read_text()+"\n[Other]\nValue=42\n")
        self.assertFalse(self.registration().changed)

    def test_owned_registration_change_is_blocked(self):
        self.commit()
        self.ini.write_text(self.ini.read_text().replace('Players=/Game','Players=/Fake'))
        with self.assertRaisesRegex(ToolError,"외부에서 수정"):
            self.registration()

    def test_manual_existing_section_not_overwritten(self):
        self.ini.parent.mkdir()
        self.ini.write_text('[UETableDesk.DataTables]\nPlayers=/Manual\n')
        with self.assertRaisesRegex(ToolError,"수기"):
            self.registration()

    def test_missing_owned_block_is_blocked(self):
        self.commit()
        self.ini.write_text('[Other]\nKey=Value\n')
        with self.assertRaisesRegex(ToolError,"없어졌습니다"):
            self.registration()

    def test_register_selected_keeps_previously_registered_others(self):
        self.commit([self.tables[1]])
        self.assertNotIn('Players=',self.ini.read_text())
        self.commit([self.tables[0]])
        self.assertIn('Players=',self.ini.read_text())
        self.assertIn('Items=',self.ini.read_text())

    def test_route_change_waits_for_successful_asset_import(self):
        self.commit()
        original=self.ini.read_bytes()
        self.project.routes['Players']='NewFolder'
        execute_plan(build_plan(self.project,[self.tables[0]]))
        self.assertEqual(original,self.ini.read_bytes())
        self.commit([self.tables[0]])
        self.assertIn('Players=/Game/DataTables/NewFolder/DT_Players.DT_Players',self.ini.read_text())
        self.assertIn('Items=/Game/DataTables/DT_Items.DT_Items',self.ini.read_text())

    def test_config_changed_after_preview_blocks_commit(self):
        plan=self.registration()
        self.ini.parent.mkdir()
        self.ini.write_text('[Other]\nRace=1\n')
        with self.assertRaisesRegex(ToolError,'미리보기 이후'):
            commit_registration(plan,self.fake_saved_files(plan))
        self.assertEqual(self.ini.read_text(),'[Other]\nRace=1\n')

    def test_cpp_changed_during_import_blocks_registration(self):
        plan=self.registration()
        path=self.project.root/self.project.subsystem_source_relative
        path.write_text(path.read_text()+'\n// race\n')
        with self.assertRaisesRegex(ToolError,'미리보기 이후'):
            commit_registration(plan,self.fake_saved_files(plan))
        self.assertFalse(self.ini.exists())

    def test_manifest_write_failure_restores_ini(self):
        from uerowforge import core
        self.ini.parent.mkdir();self.ini.write_bytes(b'[Other]\nKeep=1\n')
        before=self.ini.read_bytes()
        plan=self.registration()
        saved=self.fake_saved_files(plan)
        original=core.atomic_write
        def fail(path,data):
            if path==plan.manifest_path:
                raise OSError('manifest write failed')
            return original(path,data)
        with patch('uerowforge.core.atomic_write',side_effect=fail):
            with self.assertRaises(ToolError):
                commit_registration(plan,saved)
        self.assertEqual(before,self.ini.read_bytes())

    def test_registration_before_code_conversion_is_blocked(self):
        self.tables[0].rows[0]['ID']=123
        with self.assertRaisesRegex(ToolError,'변환을 완료'):
            build_registration_plan(build_plan(self.project,self.tables))

    def test_ini_symlink_escape_is_blocked(self):
        self.ini.parent.mkdir()
        other=Path(self.temp.name)/'outside.ini';other.write_text('[Other]')
        try:
            self.ini.symlink_to(other)
        except OSError:
            self.skipTest('Symlink unavailable')
        with self.assertRaises(ToolError):
            self.registration()
        self.assertEqual(other.read_text(),'[Other]')
