#include "TableDeskSampleGameMode.h"

#include "Data/DataTableSubsystem.h"
#include "Data/TDSStructTypes.h"
#include "Engine/Engine.h"
#include "Engine/GameInstance.h"

DEFINE_LOG_CATEGORY_STATIC(LogTableDeskSample, Log, All);

namespace
{
    void Report(const FString& Message, bool bSuccess = true)
    {
        if (bSuccess)
        {
            UE_LOG(LogTableDeskSample, Display, TEXT("%s"), *Message);
        }
        else
        {
            UE_LOG(LogTableDeskSample, Warning, TEXT("%s"), *Message);
        }

        if (GEngine)
        {
            GEngine->AddOnScreenDebugMessage(
                INDEX_NONE, 60.0f, bSuccess ? FColor::Green : FColor::Yellow,
                Message, false);
        }
    }
}

void ATableDeskSampleGameMode::BeginPlay()
{
    Super::BeginPlay();

    Report(TEXT("UE TableDesk sample: Excel -> JSON / C++ -> DataTable -> Subsystem -> Game"));
    UGameInstance* Instance = GetGameInstance();
    const UDataTableSubsystem* Tables = Instance
        ? Instance->GetSubsystem<UDataTableSubsystem>() : nullptr;
    if (!IsValid(Tables))
    {
        Report(TEXT("DataTableSubsystem is unavailable. Check the Editor build."), false);
        return;
    }

    // No fallback rows: missing assets must not look like a successful import.
    UDataTable* Players = Tables->GetPlayersTable();
    if (IsValid(Players))
    {
        // Row pointers stay local. Copy values before keeping them long-term.
        const FTDSPlayersRow* Row = Players->FindRow<FTDSPlayersRow>(
            FName(TEXT("Player_001")), TEXT("TableDeskSample"), false);
        if (Row)
        {
            Report(FString::Printf(
                TEXT("Players / Player_001: Name=%s  ID=%d  MaxHP=%d  MoveSpeed=%.1f"),
                *Row->Name.ToString(), Row->ID, Row->MaxHP, Row->MoveSpeed));
        }
        else
        {
            Report(TEXT("DT_Players has no Player_001 row. Check JSON and Import Key Field=RowName."), false);
        }
    }
    else
    {
        Report(TEXT("Players is not loaded. Create/import and register DT_Players after building, then restart PIE."), false);
    }

    UDataTable* Items = Tables->GetItemsTable();
    if (IsValid(Items))
    {
        const FTDSItemsRow* Row = Items->FindRow<FTDSItemsRow>(
            FName(TEXT("Item_001")), TEXT("TableDeskSample"), false);
        if (Row)
        {
            Report(FString::Printf(
                TEXT("Items / Item_001: Name=%s  ID=%d  Weight=%.1f"),
                *Row->Name.ToString(), Row->ID, Row->Weight));
        }
        else
        {
            Report(TEXT("DT_Items has no Item_001 row. Check JSON and Import Key Field=RowName."), false);
        }
    }
    else
    {
        Report(TEXT("Items is not loaded. Create/import and register DT_Items after building, then restart PIE."), false);
    }
}
