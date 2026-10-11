"""Regression coverage for table getters, guarded generation and older revisions."""
import copy
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from test_core import fixture, SAMPLE
from uerowforge.core import (Field, ToolError, build_plan, digest, execute_plan, header_blocks,
                            json_text, load_tables, struct_text)


class SubsystemTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = fixture(Path(self.temp.name) / "Project")
        self.tables, _ = load_tables([SAMPLE])

    def tearDown(self):
        self.temp.cleanup()

    def generate(self, tables=None):
        plan = build_plan(self.project, self.tables if tables is None else tables)
        execute_plan(plan)
        return plan

    def read(self, relative):
        return (self.project.root / relative).read_text()

    def cpp(self):
        return self.read(self.project.subsystem_source_relative)

    def header(self):
        return self.read(self.project.subsystem_header_relative)

    def test_row_policy_is_exact_readonly_plus_category(self):
        for table in self.tables:
            text = struct_text(table, self.project)
            matches = re.findall(r"UPROPERTY\(([^)]*)\)", text)
            self.assertTrue(matches)
            self.assertTrue(all(m == f'BlueprintReadOnly, Category = "{table.name}"' for m in matches))
            self.assertIn("USTRUCT(BlueprintType)", text)
            for forbidden in ("BlueprintReadWrite", "EditAnywhere", "EditDefaultsOnly", "meta"):
                self.assertNotIn(forbidden, text)

    def test_exact_fixed_class_and_explicit_private_members(self):
        self.generate()
        h, cpp = self.header(), self.cpp()
        self.assertIn("UDataTableSubsystem : public UGameInstanceSubsystem", h)
        self.assertNotIn("UOBDataTableSubsystem", h)
        self.assertNotIn("TMap", h + cpp)
        private = h.split("private:")[1]
        for table in ("Players", "Items"):
            self.assertIn(f"UPROPERTY(Transient)\n    TObjectPtr<UDataTable> {table}Table = nullptr;", private)
            self.assertIn(f"UDataTable* Get{table}Table() const", h.split("private:")[0])
            self.assertIn(f"return {table}Table.Get();", h)
            self.assertNotIn(f"Find{table}Row", h + cpp)
            self.assertNotIn(f"TryGet{table}Row", h + cpp)
        self.assertNotIn("BlueprintReadOnly", private)

    def test_generated_h_is_last_include_in_both_headers(self):
        self.generate()
        for path, final in ((self.project.header_relative, "OBStructTypes.generated.h"),
                            (self.project.subsystem_header_relative, "DataTableSubsystem.generated.h")):
            self.assertEqual(re.findall(r'^#include "(.*)"', self.read(path), re.M)[-1], final)
        self.assertFalse(list(self.project.root.rglob("*.generated.h")))

    def test_non_template_loader_init_and_deinit(self):
        self.generate()
        cpp = self.cpp()
        for table in ("Players", "Items"):
            self.assertIn(f'{table}Table = LoadTable(TEXT("{table}"), TEXT("/Game/DataTables/DT_{table}.DT_{table}"), FOB{table}Row::StaticStruct());', cpp)
            self.assertIn(f"{table}Table = nullptr;", cpp)
        self.assertIn("LoadTable(const TCHAR* TableName, const TCHAR* AssetPath, const UScriptStruct* ExpectedRowStruct)", cpp)
        self.assertIn("GetRowStruct() != ExpectedRowStruct", cpp)
        self.assertIn("!AssetPath || !*AssetPath", cpp)
        self.assertIn("!IsValid(Table)", cpp)
        self.assertEqual(cpp.count("return nullptr;"), 3)
        self.assertIn("return Table;", cpp)
        self.assertIn("Super::Initialize(Collection)", cpp)
        self.assertIn("Super::Deinitialize()", cpp)
        self.assertNotIn("GGameIni", cpp)
        self.assertNotIn("GConfig", cpp)
        self.assertNotIn("ConfigCacheIni", cpp)
        for obsolete in ("template <", "TRow", "LoadRegisteredTable<", "OutRow", "FindRow<"):
            self.assertNotIn(obsolete, cpp)

    def test_add_table_updates_members_without_removing_unselected(self):
        self.generate()
        t = copy.deepcopy(self.tables[0]);t.name = "Weapons"
        plan = self.generate([t])
        self.assertTrue(plan.code_changed)
        self.assertIn("GetWeaponsTable", plan.code_diff())
        for name in ("Players", "Items", "Weapons"):
            self.assertIn(f"{name}Table", self.header())
            self.assertIn(f"FOB{name}Row", self.read(self.project.header_relative))
        self.assertFalse(build_plan(self.project, [t]).changed)

    def test_value_only_does_not_rewrite_any_cpp_file(self):
        self.generate()
        paths = [self.project.root / p for p in (self.project.header_relative, self.project.subsystem_header_relative, self.project.subsystem_source_relative)]
        previous = [(p.read_bytes(), p.stat().st_mtime_ns) for p in paths]
        self.tables[0].rows[0]["ID"] = 111
        plan = self.generate([self.tables[0]])
        self.assertFalse(plan.code_changed)
        self.assertEqual(previous, [(p.read_bytes(), p.stat().st_mtime_ns) for p in paths])

    def test_asset_path_change_requires_cpp_rebuild(self):
        self.generate()
        self.project.asset_subdir = "OtherData"
        plan = build_plan(self.project, self.tables)
        self.assertTrue(plan.code_changed)
        self.assertIn('TEXT("/Game/OtherData/DT_Players.DT_Players")', plan.subsystem_preview())
        self.assertTrue(any("출력 경로 변경" in n for n in plan.notes))

    def test_paths_mirror_custom_header_subfolder(self):
        self.project.header_subdir = "Types/Rows"
        self.generate()
        self.assertTrue((self.project.root / "Source/OperationBreakpoint/Private/Types/Rows/DataTableSubsystem.cpp").exists())
        self.assertIn('#include "Types/Rows/DataTableSubsystem.h"', self.cpp())

    def test_empty_header_subdir_is_supported(self):
        self.project.header_subdir = ""
        self.generate()
        self.assertTrue((self.project.root / "Source/OperationBreakpoint/Private/DataTableSubsystem.cpp").exists())
        self.assertIn('#include "DataTableSubsystem.h"', self.cpp())

    def test_fixed_name_survives_prefix_change_on_fresh_project(self):
        self.project.prefix = "Other"
        self.generate()
        self.assertIn("UDataTableSubsystem", self.header())
        self.assertIn("FOtherPlayersRow::StaticStruct()", self.cpp())
        self.assertTrue((self.project.root / self.project.subsystem_header_relative).exists())

    def test_unselected_struct_tamper_blocks_generation(self):
        self.generate()
        path = self.project.root / self.project.header_relative
        path.write_text(path.read_text().replace('Category = "Items"', 'Category = "Tampered"'))
        with self.assertRaisesRegex(ToolError, "Items"):
            build_plan(self.project, [self.tables[0]])

    def test_external_subsystem_edits_block_both_files(self):
        self.generate()
        for relative in (self.project.subsystem_header_relative, self.project.subsystem_source_relative):
            with self.subTest(relative=relative):
                path = self.project.root / relative
                original = path.read_bytes()
                path.write_bytes(original + b"\n// manual change\n")
                with self.assertRaisesRegex(ToolError, "서브시스템"):
                    build_plan(self.project, self.tables)
                path.write_bytes(original)

    def test_missing_subsystem_file_is_not_silently_recreated(self):
        self.generate()
        (self.project.root / self.project.subsystem_header_relative).unlink()
        with self.assertRaisesRegex(ToolError, "없어졌습니다"):
            build_plan(self.project, self.tables)

    def test_crlf_and_utf8_bom_are_not_false_tamper(self):
        self.generate()
        path = self.project.root / self.project.subsystem_source_relative
        expected = b"\xef\xbb\xbf" + path.read_bytes().replace(b"\n", b"\r\n")
        path.write_bytes(expected)
        plan = build_plan(self.project, self.tables)
        self.assertFalse(plan.changed)
        self.assertEqual(path.read_bytes(), expected)

    def test_manual_target_file_is_never_adopted(self):
        path = self.project.root / self.project.subsystem_source_relative
        path.parent.mkdir(parents=True)
        path.write_text("// developer-owned")
        with self.assertRaisesRegex(ToolError, "수기 파일"):
            build_plan(self.project, self.tables)
        self.assertEqual(path.read_text(), "// developer-owned")
        self.assertFalse((self.project.root / self.project.header_relative).exists())

    def test_fixed_filename_collision_in_other_module(self):
        path = self.project.root / "Source/Other/Public/DataTableSubsystem.h"
        path.parent.mkdir(parents=True); path.write_text("// owned elsewhere")
        with self.assertRaisesRegex(ToolError, "고정 이름"):
            build_plan(self.project, self.tables)

    def test_class_collision_under_different_filename_in_plugin(self):
        path = self.project.root / "Plugins/Test/Source/Test/Public/Manager.h"
        path.parent.mkdir(parents=True)
        path.write_text("UCLASS()\nclass TEST_API UDataTableSubsystem : public UObject {};\n")
        with self.assertRaisesRegex(ToolError, "이미 UDataTableSubsystem"):
            build_plan(self.project, self.tables)

    def test_forward_declarations_and_comments_are_not_definitions(self):
        path = self.project.root / "Source/OperationBreakpoint/Client.h"
        path.write_text('class UDataTableSubsystem;\n// class UDataTableSubsystem {};\nconst char* S = "class UDataTableSubsystem : public UObject {}";')
        self.generate()

    def test_subsystem_race_after_preview_blocks_every_output(self):
        plan = build_plan(self.project, self.tables)
        path = self.project.root / self.project.subsystem_source_relative
        path.parent.mkdir(parents=True); path.write_text("// written during preview")
        with self.assertRaises(ToolError):
            execute_plan(plan)
        self.assertFalse((self.project.root / self.project.header_relative).exists())

    def test_late_source_write_failure_rolls_back_json_and_all_cpp(self):
        from uerowforge import core
        plan = build_plan(self.project, self.tables)
        original = core.atomic_write
        def fail(path, data):
            if path == self.project.root / self.project.subsystem_source_relative:
                raise OSError("source write failed")
            return original(path, data)
        with patch("uerowforge.core.atomic_write", side_effect=fail):
            with self.assertRaises(ToolError):
                execute_plan(plan)
        for task in plan.writes:
            self.assertFalse(task.path.exists())

    def install_v011_fixture(self):
        # Reconstruct the precise legacy field policy and v1 manifest structure.
        plan = self.generate()
        header = self.project.root / self.project.header_relative
        header.write_text(header.read_text().replace("BlueprintReadOnly, Category", "EditAnywhere, BlueprintReadWrite, Category"))
        state = json.loads(plan.manifest_path.read_bytes())
        for name, block in header_blocks(header.read_text()).items():
            state["tables"][name]["block_sha256"] = digest(block)
        # v0.1.1 stored block_sha256 before row_keys/asset_path. Preserve that
        # order to catch false manifest changes after a partial migration.
        state["tables"] = {name: {key: meta[key] for key in
                           ("schema", "json_relative", "json_sha256", "block_sha256", "row_keys", "asset_path")}
                           for name, meta in state["tables"].items()}
        state.pop("managed_files");state.pop("generator_revision")
        plan.manifest_path.write_text(json_text(state))
        for relative in (self.project.subsystem_header_relative, self.project.subsystem_source_relative):
            (self.project.root / relative).unlink()
        return plan

    def test_legacy_migration_updates_all_fields_but_not_unselected_json(self):
        self.install_v011_fixture()
        items_json = self.project.root / "DataTable/Items.json"
        before = (items_json.read_bytes(), items_json.stat().st_mtime_ns)
        plan = self.generate([self.tables[0]])
        self.assertTrue(plan.code_changed)
        self.assertTrue(any("v0.1.x 이관" in n for n in plan.notes))
        self.assertNotIn("BlueprintReadWrite", self.read(self.project.header_relative))
        self.assertNotIn("EditAnywhere", self.read(self.project.header_relative))
        self.assertIn("GetItemsTable", self.header())
        self.assertEqual(before, (items_json.read_bytes(), items_json.stat().st_mtime_ns))
        self.assertFalse(build_plan(self.project, self.tables).changed)
        self.assertFalse((self.project.root / "Config/DefaultGame.ini").exists())

    def test_legacy_migration_detects_unselected_manual_change(self):
        self.install_v011_fixture()
        path = self.project.root / self.project.header_relative
        path.write_text(path.read_text().replace('Category = "Items"', 'Category = "Changed"'))
        with self.assertRaises(ToolError):
            build_plan(self.project, [self.tables[0]])

    def test_manifest_loss_blocks_reconstruction(self):
        plan = self.generate()
        plan.manifest_path.unlink()
        with self.assertRaisesRegex(ToolError, "생성 이력이 없습니다"):
            build_plan(self.project, self.tables)

    def test_case_only_table_rename_blocked_against_manifest(self):
        self.generate()
        t = copy.deepcopy(self.tables[0]);t.name = "players"
        with self.assertRaisesRegex(ToolError, "대소문자"):
            build_plan(self.project, [t])

    def test_future_generator_version_is_not_downgraded(self):
        plan = self.generate()
        state=json.loads(plan.manifest_path.read_bytes());state["generator_revision"]=999
        plan.manifest_path.write_text(json_text(state))
        with self.assertRaisesRegex(ToolError, "최신"):
            build_plan(self.project, self.tables)
