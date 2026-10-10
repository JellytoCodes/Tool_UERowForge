using UnrealBuildTool;
using System.Collections.Generic;

public class TableDeskSampleTarget : TargetRules
{
    public TableDeskSampleTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Game;
        // The .uproject selects UE 5.8; use that engine's current defaults.
        DefaultBuildSettings = BuildSettingsVersion.Latest;
        IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
        ExtraModuleNames.Add("TableDeskSample");
    }
}
