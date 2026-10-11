"""v0.2.1 getter API and real v0.2.0 generated-file migration regression tests.

These are text/filesystem tests, not Unreal UHT, C++ or runtime tests.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import re
import shutil
import tempfile
import unittest
from unittest.mock import patch

from test_core import SAMPLE, fixture
from uerowforge.core import (Field, GENERATOR_REVISION, MANIFEST, ToolError,
                            build_plan, digest, execute_plan, json_text, load_tables, register_project)
from uerowforge.subsystem_codegen import subsystem_header, subsystem_source

LEGACY = Path(__file__).parent / "fixtures" / "v020"


class GetterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = fixture(Path(self.tmp.name) / "Project")
        self.tables, issues = load_tables([SAMPLE])
        self.assertFalse(issues)
        self.object_paths = {t.name: f"/Game/DataTables/DT_{t.name}.DT_{t.name}" for t in self.tables}

    def tearDown(self):
        self.tmp.cleanup()

    def generate(self, tables=None):
        plan = build_plan(self.project, self.tables if tables is None else tables)
        backup = execute_plan(plan)
        return plan, backup

    def read(self, relative):
        return (self.project.root / relative).read_text(encoding="utf-8")

    def install_v020(self, registered=False):
        for folder in ("Source", "DataTable"):
            shutil.copytree(LEGACY / folder, self.project.root / folder, dirs_exist_ok=True)
        manifest = (self.project.root / self.project.header_relative).parent / MANIFEST
        state = json.loads(manifest.read_bytes())
        self.assertEqual(state["generator_revision"], 2)
        # The legacy fixture comes from the unmodified v0.2.0 generator.
        self.assertIn("TryGetPlayersRow", self.read(self.project.subsystem_header_relative))
        self.assertIn("template <typename TRow>", self.read(self.project.subsystem_source_relative))
        for relative, expected_digest in state["managed_files"].items():
            self.assertEqual(digest(self.read(relative)), expected_digest)
        if registered:
            # Simulate previously saved import metadata only; no engine is run.
            registered_tables = {name: meta["asset_path"] for name, meta in state["tables"].items()}
            block = "\n".join(["; BEGIN TABLEDESK: RUNTIME",
                               "; Generated after successful asset import. Do not edit this block.",
                               "[UETableDesk.DataTables]"] +
                              [f"{name}={path}.DT_{name}" for name, path in sorted(registered_tables.items())] +
                              ["; END TABLEDESK: RUNTIME"])
            state["runtime_registration"] = {"tables": registered_tables, "block_sha256": digest(block)}
            manifest.write_text(json_text(state), encoding="utf-8")
            path = self.project.root / "Config/DefaultGame.ini"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"\xef\xbb\xbf[/Script/EngineSettings.GeneralProjectSettings]\r\nProjectName=KeepMe\r\n\r\n" +
                             (block.replace("\n", "\r\n") + "\r\n").encode("utf-8"))
        return manifest

    def snapshot(self, relative):
        path = self.project.root / relative
        return path.read_bytes(), path.stat().st_mtime_ns

    def test_getters_are_inline_pure_and_do_not_load_or_copy(self):
        header = subsystem_header(self.project, self.tables)
        public, private = header.split("private:")
        self.assertEqual(public.count('UFUNCTION(BlueprintPure, Category = "DataTable")'), len(self.tables))
        self.assertNotIn("TObjectPtr", public)
        self.assertNotIn("BlueprintReadOnly", private)
        for table in self.tables:
            match = re.search(r"UDataTable\* Get" + table.name + r"Table\(\) const\s*\{([^}]+)\}", public)
            self.assertIsNotNone(match)
            self.assertEqual(match[1].strip(), f"return {table.name}Table.Get();")
        for forbidden in ("TryGet", "FindRow", "RowName", "OutRow", "SetPlayersTable", "LoadTable"):
            self.assertNotIn(forbidden, header)

    def test_header_has_no_row_type_dependency(self):
        header = subsystem_header(self.project, self.tables)
        cpp = subsystem_source(self.project, self.tables, self.object_paths)
        self.assertIn('#include "Engine/DataTable.h"', header)
        self.assertNotIn("OBStructTypes.h", header)
        self.assertNotIn("FOBPlayersRow", header)
        self.assertIn('#include "Data/OBStructTypes.h"', cpp)
        self.assertIn("FOBPlayersRow::StaticStruct()", cpp)
        self.assertTrue(header.rstrip().endswith("};"))

    def test_rows_include_tracks_custom_and_empty_output_folder(self):
        for subdir in ("Data", "Types/Rows", ""):
            with self.subTest(subdir=subdir):
                self.project.header_subdir = subdir
                cpp = subsystem_source(self.project, self.tables, self.object_paths)
                expected = "/".join(p for p in (subdir, "OBStructTypes.h") if p)
                self.assertIn(f'#include "{expected}"', cpp)

    def test_output_deterministic_in_input_order(self):
        for render in (subsystem_header, lambda p, ts: subsystem_source(p, ts, self.object_paths)):
            self.assertEqual(render(self.project, self.tables), render(self.project, list(reversed(self.tables))))

    def test_row_schema_only_change_does_not_rewrite_subsystem(self):
        self.generate()
        paths = (self.project.subsystem_header_relative, self.project.subsystem_source_relative)
        before = {p: self.snapshot(p) for p in paths}
        players = copy.deepcopy(next(t for t in self.tables if t.name == "Players"))
        players.fields.append(Field("Stamina", "Float"))
        for row in players.rows:
            row["Stamina"] = 50.0
        plan, _ = self.generate([players])
        self.assertTrue(plan.header_changed)
        self.assertTrue(plan.code_changed)
        self.assertEqual(before, {p: self.snapshot(p) for p in paths})

    def test_generated_asset_paths_and_default_paths(self):
        self.generate()
        plan = build_plan(self.project, self.tables)
        self.assertFalse(plan.changed)
        self.assertEqual(self.project.header_subdir, "Data")
        self.assertEqual(self.project.json_subdir, "DataTable")
        self.assertTrue(all(self.project.route_for(t) == "" for t in self.tables))
        self.assertFalse((self.project.root / "Config/DefaultGame.ini").exists())
        self.assertIn('TEXT("/Game/DataTables/DT_Players.DT_Players")', plan.subsystem_preview())

    def test_converted_files_stay_unchanged_in_another_checkout(self):
        self.generate()
        copied = Path(self.tmp.name) / "different checkout"
        shutil.copytree(self.project.root, copied)
        project = register_project(copied / "OperationBreakpoint.uproject")
        plan = build_plan(project, self.tables)
        for task in plan.writes:
            self.assertEqual(task.path.read_bytes(), task.content, task.path.name)
        self.assertFalse(plan.changed)

    def test_v020_migration_updates_only_subsystem_and_manifest(self):
        manifest = self.install_v020()
        before = {p.relative_to(self.project.root).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
                  for p in self.project.root.rglob("*") if p.is_file()}
        plan = build_plan(self.project, self.tables)
        self.assertFalse(plan.header_changed)
        self.assertTrue(plan.code_changed)
        changed = {w.path.relative_to(self.project.root).as_posix() for w in plan.changed}
        self.assertEqual(changed, {self.project.subsystem_header_relative, self.project.subsystem_source_relative,
                                  manifest.relative_to(self.project.root).as_posix()})
        self.assertIn("v0.2.0 이관", plan.summary())
        self.assertIn("자동 이관하지 않습니다", plan.summary())
        self.assertIn("행 헤더를 직접 include", plan.summary())
        self.assertIn("-    bool TryGetPlayersRow", plan.code_diff())
        self.assertIn("+    UDataTable* GetPlayersTable() const", plan.code_diff())
        backup = execute_plan(plan)
        self.assertIsNotNone(backup)
        for relative in changed & before.keys():
            self.assertEqual((backup / relative).read_bytes(), before[relative][0])
        for relative in before.keys() - changed:
            self.assertEqual(self.snapshot(relative), before[relative])
        state = json.loads(manifest.read_bytes())
        self.assertEqual(state["generator_revision"], GENERATOR_REVISION)
        self.assertFalse(build_plan(self.project, self.tables).changed)
        self.assertFalse(any("v0.2.0 이관" in n for n in build_plan(self.project, self.tables).notes))

    def test_v020_partial_upgrade_preserves_unselected_and_registration(self):
        manifest = self.install_v020(registered=True)
        before_runtime = json.loads(manifest.read_bytes())["runtime_registration"]
        unchanged = ["DataTable/Items.json", "DataTable/Players.json", self.project.header_relative]
        before = {p: self.snapshot(p) for p in unchanged}
        players = next(t for t in self.tables if t.name == "Players")
        self.generate([players])
        h = self.read(self.project.subsystem_header_relative)
        self.assertIn("GetItemsTable", h)
        self.assertIn("GetPlayersTable", h)
        self.assertNotIn("TryGet", h)
        self.assertEqual(before, {p: self.snapshot(p) for p in unchanged})
        state = json.loads(manifest.read_bytes())
        self.assertNotIn("runtime_registration", state)
        for name, path in before_runtime["tables"].items():
            self.assertEqual(state["tables"][name]["asset_path"], path)
        self.assertEqual((self.project.root / "Config/DefaultGame.ini").read_bytes(),
                         b"\xef\xbb\xbf[/Script/EngineSettings.GeneralProjectSettings]\r\nProjectName=KeepMe\r\n")
        self.assertNotIn(b"BEGIN TABLEDESK: RUNTIME", (self.project.root / "Config/DefaultGame.ini").read_bytes())
        # Registration is now in code. Subsequent conversion has no INI task.
        plan = build_plan(self.project, self.tables)
        self.assertFalse(plan.changed)
        self.assertFalse(any(w.path.suffix == ".ini" for w in plan.writes))

    def test_v020_migration_with_new_table_keeps_legacy_tables(self):
        self.install_v020()
        new_table = copy.deepcopy(self.tables[0])
        new_table.name = "Weapons"
        self.generate([new_table])
        h = self.read(self.project.subsystem_header_relative)
        cpp = self.read(self.project.subsystem_source_relative)
        for name in ("Players", "Items", "Weapons"):
            self.assertIn(f"UDataTable* Get{name}Table() const", h)
            self.assertIn(f'LoadTable(TEXT("{name}"), TEXT("/Game/DataTables/DT_{name}.DT_{name}"), FOB{name}Row::StaticStruct())', cpp)
        self.assertTrue((self.project.root / "DataTable/Weapons.json").exists())

    def test_v020_upgrade_tamper_is_blocked_without_writes(self):
        self.install_v020()
        path = self.project.root / self.project.subsystem_header_relative
        original = path.read_bytes()
        manifest_path = path.parent / MANIFEST
        manifest_before = manifest_path.read_bytes()
        path.write_bytes(original + b"\n// developer edit\n")
        with self.assertRaisesRegex(ToolError, "서브시스템"):
            build_plan(self.project, self.tables)
        self.assertEqual(path.read_bytes(), original + b"\n// developer edit\n")
        self.assertEqual(manifest_path.read_bytes(), manifest_before)
        self.assertFalse((self.project.root / "Saved").exists())

    def test_v020_utf8_bom_crlf_upgrade_validates_normalized_hash(self):
        self.install_v020()
        for relative in (self.project.subsystem_header_relative, self.project.subsystem_source_relative):
            path = self.project.root / relative
            path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes().replace(b"\n", b"\r\n"))
        self.generate()
        self.assertIn("GetPlayersTable", self.read(self.project.subsystem_header_relative))
        self.assertFalse(build_plan(self.project, self.tables).changed)

    def test_v020_upgrade_write_failure_restores_original_generated_files(self):
        self.install_v020()
        plan = build_plan(self.project, self.tables)
        before = {w.path: w.path.read_bytes() if w.path.exists() else None for w in plan.writes}
        from uerowforge import core
        write = core.atomic_write
        def fail_source(path, data):
            if path == self.project.root / self.project.subsystem_source_relative:
                raise OSError("simulated migration write failure")
            return write(path, data)
        with patch("uerowforge.core.atomic_write", side_effect=fail_source):
            with self.assertRaises(ToolError):
                execute_plan(plan)
        for path, content in before.items():
            self.assertEqual(path.read_bytes() if path.exists() else None, content)

    def test_new_manifest_revision_prevents_old_generator_downgrade(self):
        plan, _ = self.generate()
        state = json.loads(plan.manifest_path.read_bytes())
        self.assertEqual(GENERATOR_REVISION, 5)
        self.assertEqual(state["generator_revision"], 5)
        # v0.2.0 accepts only 1 and 2; the upgraded format must not masquerade as 2.
        self.assertNotIn(state["generator_revision"], (1, 2, 3, 4))

    def test_migration_never_touches_other_code_or_asset_bytes(self):
        self.install_v020()
        caller = self.project.root / "Source/OperationBreakpoint/Caller.cpp"
        caller.write_text("// Existing call to be migrated manually\n// Tables->TryGetPlayersRow(...);\n", encoding="utf-8")
        asset = self.project.root / "Content/DataTables/DT_Players.uasset"
        asset.parent.mkdir(parents=True, exist_ok=True)
        asset.write_bytes(b"test sentinel - not a real Unreal package")
        paths = [caller, asset]
        before = [(p.read_bytes(), p.stat().st_mtime_ns) for p in paths]
        self.generate()
        self.assertEqual(before, [(p.read_bytes(), p.stat().st_mtime_ns) for p in paths])
