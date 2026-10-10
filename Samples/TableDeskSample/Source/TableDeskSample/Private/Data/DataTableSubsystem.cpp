// UE TABLEDESK - MANAGED SUBSYSTEM v1
// Auto-generated. Registration is committed after successful UE asset import.
#include "Data/DataTableSubsystem.h"

#include "Data/TDSStructTypes.h"
#include "CoreGlobals.h"
#include "Misc/ConfigCacheIni.h"
#include "UObject/UObjectGlobals.h"

DEFINE_LOG_CATEGORY_STATIC(LogTableDeskData, Log, All);

namespace
{
    UDataTable* LoadRegisteredTable(const TCHAR* TableName, const UScriptStruct* ExpectedRowStruct)
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

        if (Table->GetRowStruct() != ExpectedRowStruct)
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
    ItemsTable = LoadRegisteredTable(TEXT("Items"), FTDSItemsRow::StaticStruct());
    PlayersTable = LoadRegisteredTable(TEXT("Players"), FTDSPlayersRow::StaticStruct());
}

void UDataTableSubsystem::Deinitialize()
{
    ItemsTable = nullptr;
    PlayersTable = nullptr;

    Super::Deinitialize();
}
