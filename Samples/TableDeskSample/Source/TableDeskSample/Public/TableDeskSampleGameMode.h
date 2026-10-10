#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "TableDeskSampleGameMode.generated.h"

/** Consumer example, not generated code. Reads two rows once when PIE starts. */
UCLASS()
class TABLEDESKSAMPLE_API ATableDeskSampleGameMode : public AGameModeBase
{
    GENERATED_BODY()

protected:
    virtual void BeginPlay() override;
};
