// UE TABLEDESK - MANAGED SUBSYSTEM v1
// Auto-generated. Edit the Excel source, not this file.
#pragma once

#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "OBStructTypes.h"
#include "DataTableSubsystem.generated.h"

/** Read-only master data. One instance per GameInstance; game-thread use only. */
UCLASS(BlueprintType)
class OPERATIONBREAKPOINT_API UDataTableSubsystem : public UGameInstanceSubsystem
{
    GENERATED_BODY()

public:
    virtual void Initialize(FSubsystemCollectionBase& Collection) override;
    virtual void Deinitialize() override;

    // Items: do not retain the row pointer across a reimport; copy long-lived values.
    const FOBItemsRow* FindItemsRow(FName RowName) const;

    // Outputs a copy. On failure OutRow is reset to its default value.
    UFUNCTION(BlueprintCallable, BlueprintPure = false, Category = "DataTable|Items")
    bool TryGetItemsRow(FName RowName, FOBItemsRow& OutRow) const;

    // Players: do not retain the row pointer across a reimport; copy long-lived values.
    const FOBPlayersRow* FindPlayersRow(FName RowName) const;

    // Outputs a copy. On failure OutRow is reset to its default value.
    UFUNCTION(BlueprintCallable, BlueprintPure = false, Category = "DataTable|Players")
    bool TryGetPlayersRow(FName RowName, FOBPlayersRow& OutRow) const;

private:
    UPROPERTY(Transient)
    TObjectPtr<UDataTable> ItemsTable = nullptr;

    UPROPERTY(Transient)
    TObjectPtr<UDataTable> PlayersTable = nullptr;

};
