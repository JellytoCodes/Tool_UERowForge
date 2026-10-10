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
        execute_plan(build_plan(self.project,self.tables))
        self.plan=build_plan(self.project,self.tables)

    def tearDown(self):
        self.temp.cleanup()

    def popen(self, ok=True, partial=False):
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
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes(b'fixture-only: NOT a real package')
                saved.append(entry['asset_path'])
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

    def test_successful_process_commits_registration(self):
        result=self.run_fake()
        self.assertTrue(result['ok'])
        self.assertEqual(Path(result['registration_path']),self.project.root/'Config/DefaultGame.ini')
        self.assertIn('Players=',Path(result['registration_path']).read_text())
        self.assertFalse(build_plan(self.project,self.tables).changed)

    def test_failed_process_leaves_registration_unchanged(self):
        with self.assertRaisesRegex(ToolError,'반영 실패'):
            self.run_fake(ok=False,partial=True)
        self.assertFalse((self.project.root/'Config/DefaultGame.ini').exists())

    def test_false_success_with_partial_saved_list_cannot_commit(self):
        with self.assertRaisesRegex(ToolError,'등록은 완료되지'):
            self.run_fake(ok=True,partial=True)
        self.assertFalse((self.project.root/'Config/DefaultGame.ini').exists())

    def test_config_collision_blocks_before_starting_engine(self):
        ini=self.project.root/'Config/DefaultGame.ini'
        ini.parent.mkdir();ini.write_text('[UETableDesk.DataTables]\nPlayers=/Manual\n')
        with patch('uerowforge.unreal_runner.subprocess.Popen') as process:
            with self.assertRaisesRegex(ToolError,'수기'):
                run_assets(self.plan,lambda line:None)
            process.assert_not_called()


    def test_new_and_legacy_demo_markers_both_block_engine_execution(self):
        path = Path(self.project.uproject)
        original = json.loads(path.read_text())
        for key in ("UERowForgeDemo", "TableDeskDemo"):
            with self.subTest(key=key):
                path.write_text(json.dumps(dict(original, **{key: True})))
                with self.assertRaisesRegex(ToolError, "샘플 프로젝트"):
                    check_engine(self.plan)
