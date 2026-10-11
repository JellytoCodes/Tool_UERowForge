// UE TABLEDESK - MANAGED HEADER v1
// Edit Excel source; only marked blocks are maintained by TableDesk.
#pragma once

#include "CoreMinimal.h"
#include "Engine/DataTable.h"
#include "OBStructTypes.generated.h"


// BEGIN TABLEDESK: Items
USTRUCT(BlueprintType)
struct OPERATIONBREAKPOINT_API FOBItemsRow : public FTableRowBase
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category = "Items")
    FString RawName = TEXT("");

    UPROPERTY(BlueprintReadOnly, Category = "Items")
    FName Name = NAME_None;

    UPROPERTY(BlueprintReadOnly, Category = "Items")
    int32 ID = 0;

    UPROPERTY(BlueprintReadOnly, Category = "Items")
    float Weight = 0.0f;

    UPROPERTY(BlueprintReadOnly, Category = "Items")
    bool bEnabled = false;

};
// END TABLEDESK: Items

// BEGIN TABLEDESK: Players
USTRUCT(BlueprintType)
struct OPERATIONBREAKPOINT_API FOBPlayersRow : public FTableRowBase
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category = "Players")
    FString RawName = TEXT("");

    UPROPERTY(BlueprintReadOnly, Category = "Players")
    FName Name = NAME_None;

    UPROPERTY(BlueprintReadOnly, Category = "Players")
    int32 ID = 0;

    UPROPERTY(BlueprintReadOnly, Category = "Players")
    int32 MaxHP = 0;

    UPROPERTY(BlueprintReadOnly, Category = "Players")
    float MoveSpeed = 0.0f;

    UPROPERTY(BlueprintReadOnly, Category = "Players")
    bool bEnabled = false;

};
// END TABLEDESK: Players
