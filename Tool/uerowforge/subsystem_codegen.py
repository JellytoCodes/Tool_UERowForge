"""Deterministic C++ for an explicit-member GameInstance subsystem.

Generate one private UDataTable reference and one public table getter per schema.
Row lookup belongs to the caller. This module formats text only; guarded disk
writes and migration checks live in core.py.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .core import Project, Table

# Compatibility identifiers (including log labels in generated C++) remain
# byte-identical to v0.2.2: an app rename must not rewrite game project code.
# The manifest's generator_revision tracks actual output/API changes.
SUBSYSTEM_MARKER = "// UE TABLEDESK - MANAGED SUBSYSTEM v1"
RUNTIME_SECTION = "UETableDesk.DataTables"


def subsystem_header(project: Project, tables: list[Table]) -> str:
    lines = [SUBSYSTEM_MARKER,
             "// Auto-generated. Edit the Excel source, not this file.",
             "#pragma once", "", '#include "CoreMinimal.h"',
             '#include "Engine/DataTable.h"',
             '#include "Subsystems/GameInstanceSubsystem.h"',
             '#include "DataTableSubsystem.generated.h"', "",
             "/** Per-GameInstance table cache. Game-thread use; returned tables are shared objects. */",
             "UCLASS(BlueprintType)",
             f"class {project.module.upper()}_API UDataTableSubsystem : public UGameInstanceSubsystem",
             "{", "    GENERATED_BODY()", "", "public:",
             "    virtual void Initialize(FSubsystemCollectionBase& Collection) override;",
             "    virtual void Deinitialize() override;", "",
             "    // Getters return nullptr if the table could not be loaded."]
    for table in sorted(tables, key=lambda t: t.name):
        lines += ['    UFUNCTION(BlueprintPure, Category = "DataTable")',
                  f"    UDataTable* Get{table.name}Table() const",
                  "    {", f"        return {table.name}Table.Get();", "    }", ""]
    lines += ["private:"]
    for table in sorted(tables, key=lambda t: t.name):
        lines += ["    UPROPERTY(Transient)",
                  f"    TObjectPtr<UDataTable> {table.name}Table = nullptr;", ""]
    return "\n".join(lines + ["};", ""])


def subsystem_source(project: Project, tables: list[Table]) -> str:
    include_path = "/".join(x for x in (project.header_subdir, "DataTableSubsystem.h") if x)
    rows_include = "/".join(x for x in (project.header_subdir, project.header_name) if x)
    lines = [SUBSYSTEM_MARKER,
             "// Auto-generated. Registration is committed after successful UE asset import.",
             f'#include "{include_path}"', "", f'#include "{rows_include}"',
             '#include "CoreGlobals.h"', '#include "Misc/ConfigCacheIni.h"',
             '#include "UObject/UObjectGlobals.h"', "",
             "DEFINE_LOG_CATEGORY_STATIC(LogTableDeskData, Log, All);", "",
             "namespace", "{",
             "    UDataTable* LoadRegisteredTable(const TCHAR* TableName, const UScriptStruct* ExpectedRowStruct)",
             "    {", "        FString AssetPath;",
             f'        if (!GConfig || !GConfig->GetString(TEXT("{RUNTIME_SECTION}"), TableName, AssetPath, GGameIni)',
             "            || AssetPath.IsEmpty())", "        {",
             '            UE_LOG(LogTableDeskData, Warning, TEXT("Table %s is not registered. Import its asset with TableDesk first."), TableName);',
             "            return nullptr;", "        }", "",
             "        UDataTable* Table = LoadObject<UDataTable>(nullptr, *AssetPath);",
             "        if (!IsValid(Table))", "        {",
             '            UE_LOG(LogTableDeskData, Error, TEXT("Failed to load %s: %s"), TableName, *AssetPath);',
             "            return nullptr;", "        }", "",
             "        if (Table->GetRowStruct() != ExpectedRowStruct)", "        {",
             '            UE_LOG(LogTableDeskData, Error, TEXT("Unexpected row struct for %s: %s"), TableName, *AssetPath);',
             "            return nullptr;", "        }", "        return Table;", "    }", "}", "",
             "void UDataTableSubsystem::Initialize(FSubsystemCollectionBase& Collection)", "{",
             "    Super::Initialize(Collection);", "",
             "    // Small master tables are synchronously loaded once per GameInstance."]
    for table in sorted(tables, key=lambda t: t.name):
        lines.append(f'    {table.name}Table = LoadRegisteredTable(TEXT("{table.name}"), {table.cpp_name(project.prefix)}::StaticStruct());')
    lines += ["}", "", "void UDataTableSubsystem::Deinitialize()", "{"]
    for table in sorted(tables, key=lambda t: t.name):
        lines.append(f"    {table.name}Table = nullptr;")
    return "\n".join(lines + ["", "    Super::Deinitialize();", "}", ""])
