using UnrealBuildTool;
using System.Collections.Generic;

public class TableDeskSampleEditorTarget : TargetRules
{
    public TableDeskSampleEditorTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Editor;
        // The .uproject selects UE 5.8; use that engine's current defaults.
        DefaultBuildSettings = BuildSettingsVersion.Latest;
        IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
        ExtraModuleNames.Add("TableDeskSample");
    }
}
