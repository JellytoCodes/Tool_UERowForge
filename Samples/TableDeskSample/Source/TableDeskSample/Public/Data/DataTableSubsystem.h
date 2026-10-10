// UE TABLEDESK - MANAGED SUBSYSTEM v1
// Auto-generated. Edit the Excel source, not this file.
#pragma once

#include "CoreMinimal.h"
#include "Engine/DataTable.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "DataTableSubsystem.generated.h"

/** Per-GameInstance table cache. Game-thread use; returned tables are shared objects. */
UCLASS(BlueprintType)
class TABLEDESKSAMPLE_API UDataTableSubsystem : public UGameInstanceSubsystem
{
    GENERATED_BODY()

public:
    virtual void Initialize(FSubsystemCollectionBase& Collection) override;
    virtual void Deinitialize() override;

    // Getters return nullptr if the table could not be loaded.
    UFUNCTION(BlueprintPure, Category = "DataTable")
    UDataTable* GetItemsTable() const
    {
        return ItemsTable.Get();
    }

    UFUNCTION(BlueprintPure, Category = "DataTable")
    UDataTable* GetPlayersTable() const
    {
        return PlayersTable.Get();
    }

private:
    UPROPERTY(Transient)
    TObjectPtr<UDataTable> ItemsTable = nullptr;

    UPROPERTY(Transient)
    TObjectPtr<UDataTable> PlayersTable = nullptr;

};
