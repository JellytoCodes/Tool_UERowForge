"""Resource and entry-point checks; independent of user-owned Samples contents."""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tabledesk.gui import readme_path
from tabledesk.unreal_runner import resource_root

TOOL = Path(__file__).resolve().parents[1]
REPO = TOOL.parent


class ResourcePathTests(unittest.TestCase):
    def test_resource_root_still_resolves_the_unreal_bridge(self):
        self.assertEqual(resource_root(), TOOL)
        self.assertTrue((resource_root() / 'tabledesk/unreal_bridge.py').is_file())

    def test_template_is_bundled_independently_of_user_samples(self):
        from tabledesk.core import load_tables
        template = resource_root() / 'resources/TableTemplate.xlsx'
        self.assertTrue(template.is_file())
        tables, issues = load_tables([template])
        self.assertFalse(issues)
        self.assertEqual([t.name for t in tables], ['Players', 'Items'])
        self.assertTrue(all(t.valid for t in tables))
        self.assertEqual(sum(len(t.rows) for t in tables), 6)

    def test_source_help_resolves_repository_readme(self):
        with patch.object(sys, 'frozen', False, create=True):
            self.assertEqual(readme_path(), REPO / 'README.md')
        self.assertTrue(readme_path().is_file())

    def test_frozen_help_resolves_bundled_readme(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / '_internal'
            with patch('tabledesk.gui.resource_root', return_value=root), \
                 patch.object(sys, 'frozen', True, create=True):
                self.assertEqual(readme_path(), root / 'README.md')

    def test_packaging_sources_exist_and_exclude_user_projects(self):
        batch = (TOOL / 'build_windows.bat').read_text()
        sources = re.findall(r'--add-data "([^:"]+):([^\"]+)"', batch)
        self.assertEqual(sources, [
            ('resources', 'resources'), ('../README.md', '.'),
            ('../LICENSE.txt', '.'), ('tabledesk/unreal_bridge.py', 'tabledesk')])
        for source, _ in sources:
            path = (TOOL / source).resolve()
            self.assertTrue(path.exists(), source)
            self.assertNotIn(REPO / 'Samples', (path, *path.parents))
        self.assertIn('cd /d "%~dp0"', batch)
        self.assertNotIn('scripts/', batch)
        self.assertNotIn('docs:', batch)

    def test_cli_works_from_an_unrelated_working_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable, str(TOOL / 'main.py'), '--validate',
                 str(TOOL / 'resources/TableTemplate.xlsx')],
                cwd=tmp, capture_output=True, text=True, encoding='utf-8',
                timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload['ok'])
        self.assertEqual(sum(t['rows'] for t in payload['tables']), 6)

    def test_ci_runs_commands_from_tool_directory(self):
        workflow = (REPO / '.github/workflows/ci.yml').read_text()
        self.assertIn('working-directory: Tool', workflow)
        self.assertIn('python main.py --validate resources/TableTemplate.xlsx', workflow)
        self.assertIn('python -m unittest discover -s tests', workflow)
        self.assertIn('python3 tests/gui_smoke.py', workflow)
        self.assertTrue((TOOL / 'tests/gui_smoke.py').is_file())

    def test_old_fixture_line_endings_are_protected_at_new_path(self):
        self.assertIn('Tool/tests/fixtures/** -text',
                      (REPO / '.gitattributes').read_text())


if __name__ == '__main__':
    unittest.main()
