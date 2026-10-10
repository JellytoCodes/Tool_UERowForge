// UE TABLEDESK - MANAGED SUBSYSTEM v1
// Auto-generated. Registration is committed after successful UE asset import.
#include "Data/DataTableSubsystem.h"

#include "CoreGlobals.h"
#include "Misc/ConfigCacheIni.h"
#include "UObject/UObjectGlobals.h"

DEFINE_LOG_CATEGORY_STATIC(LogTableDeskData, Log, All);

namespace
{
    template <typename TRow>
    UDataTable* LoadRegisteredTable(const TCHAR* TableName)
    {
        FString AssetPath;
        if (!GConfig || !GConfig->GetString(TEXT("UETableDesk.DataTables"), TableName, AssetPath, GGameIni)
            || AssetPath.IsEmpty())
        {
            UE_LOG(LogTableDeskData, Warning, TEXT("Table %s is not registered. Import its asset with TableDesk first."), TableName);
            return nullptr;
        }

        UDataTable* Table = LoadObject<UDataTable>(nullptr, *AssetPath);
        if (!IsValid(Table))
        {
            UE_LOG(LogTableDeskData, Error, TEXT("Failed to load %s: %s"), TableName, *AssetPath);
            return nullptr;
        }

        if (Table->GetRowStruct() != TRow::StaticStruct())
        {
            UE_LOG(LogTableDeskData, Error, TEXT("Unexpected row struct for %s: %s"), TableName, *AssetPath);
            return nullptr;
        }
        return Table;
    }
}

void UDataTableSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
    Super::Initialize(Collection);

    // Small master tables are synchronously loaded once per GameInstance.
    ItemsTable = LoadRegisteredTable<FOBItemsRow>(TEXT("Items"));
    PlayersTable = LoadRegisteredTable<FOBPlayersRow>(TEXT("Players"));
}

void UDataTableSubsystem::Deinitialize()
{
    ItemsTable = nullptr;
    PlayersTable = nullptr;

    Super::Deinitialize();
}

const FOBItemsRow* UDataTableSubsystem::FindItemsRow(FName RowName) const
{
    if (!IsInGameThread() || !IsValid(ItemsTable.Get()) || RowName.IsNone()
        || ItemsTable->GetRowStruct() != FOBItemsRow::StaticStruct())
    {
        return nullptr;
    }

    return ItemsTable->FindRow<FOBItemsRow>(RowName, TEXT("UDataTableSubsystem::FindItemsRow"), false);
}

bool UDataTableSubsystem::TryGetItemsRow(FName RowName, FOBItemsRow& OutRow) const
{
    if (const FOBItemsRow* Row = FindItemsRow(RowName))
    {
        OutRow = *Row;
        return true;
    }

    OutRow = FOBItemsRow{};
    return false;
}

const FOBPlayersRow* UDataTableSubsystem::FindPlayersRow(FName RowName) const
{
    if (!IsInGameThread() || !IsValid(PlayersTable.Get()) || RowName.IsNone()
        || PlayersTable->GetRowStruct() != FOBPlayersRow::StaticStruct())
    {
        return nullptr;
    }

    return PlayersTable->FindRow<FOBPlayersRow>(RowName, TEXT("UDataTableSubsystem::FindPlayersRow"), false);
}

bool UDataTableSubsystem::TryGetPlayersRow(FName RowName, FOBPlayersRow& OutRow) const
{
    if (const FOBPlayersRow* Row = FindPlayersRow(RowName))
    {
        OutRow = *Row;
        return true;
    }

    OutRow = FOBPlayersRow{};
    return false;
}
