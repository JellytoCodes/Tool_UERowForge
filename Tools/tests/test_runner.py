"""Mocked external-process tests. No Unreal installation is used."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from test_core import fixture, SAMPLE
from uerowforge.core import ToolError, build_plan, execute_plan, load_tables
from uerowforge.unreal_runner import run_assets, check_engine


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.project=fixture(self.root/'Project')
        self.project.engine_cmd=str(self.root/'UnrealEditor-Cmd.exe')
        Path(self.project.engine_cmd).write_bytes(b'fixture: NOT executable')
        self.tables,_=load_tables([SAMPLE])
        self.ini = self.project.root / 'Config/DefaultGame.ini'
        self.ini.parent.mkdir()
        self.ini.write_bytes(b'[Other]\r\nKeep=1\r\n')
        execute_plan(build_plan(self.project,self.tables))
        self.plan=build_plan(self.project,self.tables)

    def tearDown(self):
        self.temp.cleanup()

    def popen(self, ok=True, partial=False, missing_files=False, edit_code=False, edit_config=False):
        def fake(command, **kwargs):
            bridge = Path(kwargs['env']['UEROWFORGE_BRIDGE'])
            self.assertEqual(bridge.parent.name, "uerowforge")
            self.assertTrue(bridge.is_file())
            self.assertIn("UEROWFORGE_BRIDGE", " ".join(command))
            job=json.loads(Path(kwargs['env']['UEROWFORGE_JOB']).read_text())
            self.assertEqual(len(job['code_files']),3)
            saved=[]
            jobs=job['tables'][:1] if partial else job['tables']
            for entry in jobs:
                path=self.project.root/'Content'/(entry['asset_path'][6:]+'.uasset')
                if not missing_files:
                    path.parent.mkdir(parents=True,exist_ok=True)
                    path.write_bytes(b'fixture-only: NOT a real package')
                saved.append(entry['asset_path'])
            if edit_code:
                source = self.project.root / self.project.subsystem_source_relative
                source.write_bytes(source.read_bytes() + b'\n// external edit during import\n')
            if edit_config:
                ini = self.project.root / 'Config/DefaultGame.ini'
                ini.write_bytes(ini.read_bytes() + b'\n[Other]\nRace=1\n')
            Path(job['result_path']).write_text(json.dumps({'ok':ok,'saved':saved,'backup':'test-backup','error':'' if ok else 'simulated'}))
            class Process:
                stdout=io.StringIO('[UEROWFORGE] fake external process\n')
                def __enter__(self):return self
                def __exit__(self,*args):return False
                def wait(self):return 0 if ok else 1
            return Process()
        return fake

    def run_fake(self, **kwargs):
        with patch('uerowforge.unreal_runner.app_dir',return_value=self.root/'App'), \
             patch('uerowforge.unreal_runner.subprocess.Popen',side_effect=self.popen(**kwargs)):
            return run_assets(self.plan,lambda line:None)

    def test_successful_process_uses_code_paths_without_ini_registration(self):
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in [w.path for w in self.plan.writes] + [self.ini]}
        result=self.run_fake()
        self.assertTrue(result['ok'])
        self.assertNotIn('registration_path', result)
        self.assertNotIn('registration_backup', result)
        self.assertFalse(build_plan(self.project,self.tables).changed)
        self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before})

    def test_failed_process_leaves_registration_unchanged(self):
        ini = self.project.root/'Config/DefaultGame.ini'
        before = (ini.read_bytes(), ini.stat().st_mtime_ns)
        with self.assertRaisesRegex(ToolError,'반영 실패'):
            self.run_fake(ok=False,partial=True)
        self.assertEqual(before, (ini.read_bytes(), ini.stat().st_mtime_ns))

    def test_false_success_with_partial_saved_list_cannot_commit(self):
        ini = self.project.root/'Config/DefaultGame.ini'
        before = (ini.read_bytes(), ini.stat().st_mtime_ns)
        with self.assertRaisesRegex(ToolError,'에셋 저장 결과/변환 파일 확인 실패'):
            self.run_fake(ok=True,partial=True)
        self.assertEqual(before, (ini.read_bytes(), ini.stat().st_mtime_ns))

    def test_manual_legacy_config_is_ignored_by_asset_job(self):
        ini=self.project.root/'Config/DefaultGame.ini'
        ini.write_bytes(ini.read_bytes() + b'\n[UETableDesk.DataTables]\nPlayers=/Manual\n')
        before = ini.read_bytes()
        self.assertTrue(self.run_fake()['ok'])
        self.assertEqual(ini.read_bytes(), before)

    def test_code_changed_before_job_blocks_engine_execution(self):
        source = self.project.root / self.project.subsystem_source_relative
        source.write_bytes(source.read_bytes() + b'\n// external edit\n')
        with patch('uerowforge.unreal_runner.subprocess.Popen') as process:
            with self.assertRaisesRegex(ToolError, '미리보기 이후'):
                run_assets(self.plan, lambda line:None)
            process.assert_not_called()

    def test_saved_list_without_disk_files_is_rejected(self):
        before = {w.path: (w.path.read_bytes(), w.path.stat().st_mtime_ns) for w in self.plan.writes}
        with self.assertRaisesRegex(ToolError, '에셋 파일을 찾지 못'):
            self.run_fake(missing_files=True)
        self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before})

    def test_code_changed_during_import_is_detected_without_ini_write(self):
        ini = self.project.root / 'Config/DefaultGame.ini'
        before = (ini.read_bytes(), ini.stat().st_mtime_ns)
        with self.assertRaisesRegex(ToolError, '미리보기 이후'):
            self.run_fake(edit_code=True)
        self.assertEqual(before, (ini.read_bytes(), ini.stat().st_mtime_ns))

    def test_unrelated_config_change_during_import_is_allowed_and_preserved(self):
        ini = self.project.root / 'Config/DefaultGame.ini'
        before = ini.read_bytes()
        self.assertTrue(self.run_fake(edit_config=True)['ok'])
        self.assertEqual(ini.read_bytes(), before + b'\n[Other]\nRace=1\n')


    def test_new_and_legacy_demo_markers_both_block_engine_execution(self):
        path = Path(self.project.uproject)
        original = json.loads(path.read_text())
        for key in ("UERowForgeDemo", "TableDeskDemo"):
            with self.subTest(key=key):
                path.write_text(json.dumps(dict(original, **{key: True})))
                with self.assertRaisesRegex(ToolError, "샘플 프로젝트"):
                    check_engine(self.plan)
