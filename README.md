# UE TableDesk

엑셀에서 Unreal DataTable용 JSON·행 구조체·관리 서브시스템을 생성하는 Python/Tkinter 도구입니다.
프로그램 하나에 여러 프로젝트를 등록하며, 대상 프로젝트 안에 도구를 설치하지 않습니다.

**v0.2.2 / generator revision 3 / 프로토타입.** UE 5.8 소스 샘플 프로젝트를 추가했습니다. 변환·등록 규칙은 그대로입니다.
코드를 수정하는 작업자는 [AGENTS.md](AGENTS.md)를 확인하세요. 사용법과 남은 작업은 이 문서에서 관리합니다.

## 실행

Python 3.10 이상과 Tkinter가 필요하며, 앱 실행용 외부 패키지는 없습니다.

```powershell
python main.py         # 일반 실행; Windows에서는 run.bat도 가능
python main.py --demo  # 변환 테스트용 모형 프로젝트; run_demo.bat과 동일
```

`--demo`와 **변환 UI 데모** 버튼은 안전한 모형 프로젝트를 사용하므로 빌드·에셋 반영에 사용하지 않습니다.
실제 C++ 프로젝트 구성은 아래 [UE 5.8 샘플](#ue-58-샘플)에서 확인합니다.
EXE가 필요해지면 Windows에서 아래 명령으로 만들고 `dist/UETableDesk/` **폴더 전체**를 배포합니다.
이 패키지에는 미리 빌드한 EXE가 없으며 Windows 빌드·실행은 아직 미검증입니다.

```powershell
py -3 -m pip install pyinstaller
.\build_windows.bat
```

## 사용법

**프로젝트 추가 → `.uproject` 폴더 선택 → 모듈·접두사·하위 경로 설정 → 엑셀 불러오기 → 검증 → 선택 항목 변환.**
최종 확인 창에서 파일 경로와 코드 변경점을 확인한 뒤 저장합니다. 엑셀을 수정한 뒤에는 `다시 읽기 / 검증`을 누르세요.

프로젝트 루트는 작업 화면에서 고정되며 출력 하위 경로만 지정합니다. 엑셀은 프로젝트 밖에서 불러와도 됩니다.
등록 해제는 앱의 목록만 제거하며 프로젝트 파일은 삭제하지 않습니다.
현재는 `Source/<Module>/<Module>.Build.cs`가 있는 C++ 프로젝트 모듈만 지원합니다.

### 엑셀 규격

[샘플 엑셀](Samples/TableDeskSample/Excel/TableTemplate.xlsx)을 복사해 사용하세요. **시트 하나가 테이블 하나**이며 파일 여러 개를 불러올 수 있습니다.
`_Guide`처럼 `_`로 시작하는 시트는 설명용입니다.

| 행 | A | B | C | D | E |
|---|---|---|---|---|---|
| 1 | TableName | Players | 빈 칸 | SubPath | 빈 칸 |
| 2 | RowName | RawName | Name | ID | … |
| 3 | RowKey | String | Name | Int | … |
| 4 이후 | Player_001 | 기본 플레이어 | PlayerBasic | 1 | … |

E1은 선택적 추가 하위 경로이며 D1/E1은 생략할 수 있습니다. 앱에서 저장한 경로가 엑셀보다 우선합니다.
기본값은 **빈 문자열**입니다. `Null`, `None`, `(없음)`을 직접 입력하지 않습니다.

| 타입 | C++ | 빈 셀 |
|---|---|---|
| RowKey | 행 키; 일반 멤버로 생성하지 않음 | 오류 |
| String / FString | FString | 빈 문자열 |
| Name / FName | FName | NAME_None |
| Int / int32 | int32 | 오류 |
| Float | float | 오류 |
| Bool | bool | 오류 |

타입명은 대소문자를 구분하지 않습니다. Bool은 TRUE/FALSE 또는 1/0, 문자열·Name·행 키는 텍스트 셀로 입력합니다.
첫 컬럼은 `RowName / RowKey`로 고정합니다. `RawName`은 일반 필드이며 `Name` 필드와 행 키는 별개입니다.
테이블/필드명은 영문으로 시작하는 영문·숫자·밑줄 조합, 행 키는 영문·숫자·밑줄·하이픈 1~128자입니다.
예약 이름과 대소문자만 다른 중복은 차단하며 행 키 `None`은 사용할 수 없습니다.

**미지원:** xls/xlsm, 수식, 날짜/시간, 병합 셀, 배열, Enum, FText, 중첩 구조체, 에셋 참조.
수식은 값으로 붙여넣은 뒤 사용하세요. 빈 테이블로 기존 데이터를 지우는 작업은 지원하지 않습니다.
입력 상한은 파일 32 MiB, 압축 해제 합계 96 MiB, 시트 XML 32 MiB, 전체 비어 있지 않은 셀 250,000개,
테이블당 50,000행/128열입니다. 화면의 200행 미리보기 제한과 달리 JSON에는 전체 검증 데이터를 저장합니다.

### 출력과 미리보기

접두사 `OB`, 모듈 `OperationBreakpoint`를 사용한 기본 경로입니다.

```text
OperationBreakpoint/
├─ Source/OperationBreakpoint/
│  ├─ Public/Data/
│  │  ├─ OBStructTypes.h
│  │  ├─ DataTableSubsystem.h
│  │  └─ .tabledesk-manifest.json
│  └─ Private/Data/DataTableSubsystem.cpp
├─ DataTable/Players.json
└─ Content/DataTables/DT_Players.uasset  # 별도 에셋 반영 단계
```

추가 하위 경로는 기본적으로 없습니다. `Player → DT_Player`, `Players → DT_Players`이며 이름을 임의 변형하지 않습니다.
행 필드는 `BlueprintReadOnly + Category`, 관리 클래스는 `UDataTableSubsystem : public UGameInstanceSubsystem`으로 고정합니다.
서브시스템은 테이블마다 private `TObjectPtr<UDataTable>`와 public `Get<Table>Table()` 하나를 생성합니다.
실제 생성 예시는 [Samples/TableDeskSample](Samples/TableDeskSample)에 있습니다. 샘플의 접두사는 `TDS`, 모듈은 `TableDeskSample`입니다.

**데이터/JSON은 개별 테이블**, **C++는 공통 파일 세 개 전체**를 보여줍니다.
공통 미리보기는 정상 입력 전체와 기존 관리 테이블을 합치며 테이블 선택에 따라 바뀌지 않습니다.
실제 변환은 선택한 입력과 기존 보존분을 사용하므로 **최종 확인 창이 실제 저장 결과의 기준**입니다.
미선택 테이블은 삭제하지 않고, 데이터만 바뀌면 동일한 C++는 다시 저장하지 않습니다.

Getter는 공유 원본 객체를 반환합니다. 호출 측에서 null·행 없음 처리와 원본 변경 금지 규칙을 지키세요.
행 타입을 쓰는 C++ 파일은 `Data/OBStructTypes.h`를 직접 include해야 합니다.
BP는 Getter → 유효성 확인 → 엔진 행 조회 노드를 사용하는 방향이며, 동적 테이블의 출력 행 타입 연결은 실제 UE 검증 대상입니다.
현재 체력 같은 런타임 상태는 마스터 테이블과 분리하고, 재임포트·종료를 넘겨 사용할 행 값은 복사하세요.

## 에셋·빌드·등록: 현재 가능한 범위

| 작업 | 현재 동작 |
|---|---|
| 일반 변환 | JSON·C++·생성 이력 생성. **INI는 쓰지 않음** |
| 값 수정·같은 구조의 행 추가/삭제 | 해당 변경 때문에 C++ 재빌드 불필요 |
| 새 테이블·컬럼·타입 등 코드 변경 | 에셋 반영 전에 해당 코드의 Editor 타깃 빌드 필요 |
| UE 에셋 반영 | 실험 기능. Row Struct 지정·JSON 입력·생성/갱신·저장 |
| Subsystem 등록 | **선택 에셋 전체 저장 성공 후에만** `Config/DefaultGame.ini` 갱신 |
| 사전 예정 경로 등록 / 자동 빌드 / 자동 쿠킹 | 미구현 |

실험 기능은 프로젝트 복사본에서 시험하세요. 프로젝트의 Python Editor Script Plugin / Editor Scripting Utilities를 준비하고,
에디터를 종료한 상태에서 Editor 타깃을 빌드한 다음 프로젝트에 맞는 `UnrealEditor-Cmd.exe`를 설정해 `UE 에셋 반영`을 실행합니다.
프로젝트 플러그인 활성화, `.Build.cs` 의존성 변경, 엔진 선택·빌드는 앱이 자동 처리하지 않습니다.
신규 구조체는 **에셋을 생성하는 PC에서도** 빌드된 상태여야 합니다.

JSON 임포트 키는 `RowName`이고 기존 데이터를 전체 입력으로 교체합니다. 다른 에셋 종류·다른 Row Struct는 덮어쓰지 않습니다.
성공 후 INI의 `UETableDesk.DataTables` 구역에 `Players=/Game/DataTables/DT_Players.DT_Players`처럼 등록하고,
다음 게임 시작 때 로드·행 타입 검사 후 보관합니다. 로드 실패는 로그와 null로 처리하며 자동 재시도하지 않습니다.

**현재는 같은 경로에 에셋을 수동 생성한 것만으로 INI 등록까지 자동 완료되지는 않습니다.**
에셋의 부분 저장 후 실패가 가능하며, 전체 롤백·실행 중인 다른 에디터 감지·최신 컴파일 타입 검증을 보장하지 않습니다.
일반 Reimport 메뉴의 원본 경로 메타데이터와 패키징 시 쿠킹 포함 여부도 별도 확인이 필요합니다.

## UE 5.8 샘플

**게임 콘텐츠가 아니라 데이터 연결 흐름만 확인하는 최소 C++ 프로젝트**입니다. 기존 `examples/`의 엑셀과 출력 예시를 이곳으로 모았습니다.

```text
Samples/TableDeskSample/
├─ TableDeskSample.uproject           # EngineAssociation: 5.8
├─ Excel/TableTemplate.xlsx           # Players / Items, 각 3행
├─ DataTable/Players.json, Items.json
├─ Config/                           # 기본 GameMode / 시작 맵 설정
├─ Content/DataTables/               # 에셋을 생성할 위치; 현재 에셋 미포함
└─ Source/
   ├─ TableDeskSample.Target.cs
   ├─ TableDeskSampleEditor.Target.cs
   └─ TableDeskSample/
      ├─ TableDeskSample.Build.cs
      ├─ Public/Data/TDSStructTypes.h
      ├─ Public/Data/DataTableSubsystem.h
      ├─ Public/Data/.tabledesk-manifest.json
      ├─ Private/Data/DataTableSubsystem.cpp
      └─ Public·Private/TableDeskSampleGameMode.h·cpp
```

**포함된 것은 소스 프로젝트입니다.** `.uasset`, 프로젝트 `.umap`, 빌드 바이너리는 아직 없습니다.
에셋을 준비하면 `TableDeskSampleGameMode`가 PIE 시작 시 `GetPlayersTable()` / `GetItemsTable()`에서 행을 읽어 화면과 Output Log에 출력하도록 작성했습니다.
현재 샘플 값은 `Player_001: MaxHP=100, MoveSpeed=600`, `Item_001: Weight=1.5`입니다.
에셋·등록이 없으면 준비 필요 메시지를 출력하며, 임시 데이터로 성공한 것처럼 대체하지 않습니다.

### 최초 확인 순서

1. 툴에서 `Samples/TableDeskSample` 폴더를 **프로젝트 추가**로 등록합니다. 모듈 `TableDeskSample`, 접두사 `TDS`, 나머지는 기본 경로로 둡니다. `Excel/TableTemplate.xlsx`를 불러오세요. 동일 입력은 포함된 생성물과 같으므로 다시 변환해도 변경이 없습니다.
2. UE **5.8**에 연결한 `.uproject`에서 프로젝트 파일을 생성하고, `TableDeskSampleEditor / Development Editor / Win64`를 빌드합니다. **미리보기의 ‘C++ 변경 없음’이 최초 빌드 완료를 의미하지는 않습니다.** 소스 빌드 엔진은 해당 설치로 Switch Unreal Engine Version을 지정합니다.
3. 에디터를 닫고 툴에 해당 5.8의 `UnrealEditor-Cmd.exe`를 지정한 뒤 두 테이블을 선택해 **UE 에셋 반영(실험)**을 실행합니다. `DT_Players` / `DT_Items`와 런타임 INI 등록이 모두 성공했는지 확인합니다. Python 관련 내장 플러그인은 샘플 `.uproject`에만 활성화해 두었습니다.
4. 에디터를 다시 열어 **Play**합니다. 화면 및 Output Log의 `LogTableDeskSample`을 확인하세요. 엔진의 빈 `/Engine/Maps/Entry`를 시작 맵으로 지정했으므로 별도 장면 제작은 필요하지 않은 구성입니다. 설치 환경에서 이 맵을 열 수 없다면 빈 레벨을 만들고 GameMode Override를 `TableDeskSampleGameMode`로 지정합니다.

값 변경 확인은 엑셀의 `Player_001.MaxHP`를 100 → 150으로 수정 → 다시 읽기/변환 → 에셋 갱신 → PIE 재시작 순서입니다.
값만 변경했다면 C++ 재빌드는 필요 없으며, JSON만 수정하고 에셋을 갱신하지 않으면 게임 값도 바뀌지 않습니다.

<details>
<summary>에셋을 수동으로 만들 때</summary>

빌드 후 `/Game/DataTables`에 `DT_Players`(`FTDSPlayersRow`), `DT_Items`(`FTDSItemsRow`)를 생성합니다.
각 에셋의 **Import Key Field를 `RowName`**으로 지정하고 대응 JSON을 입력한 뒤 저장합니다.
현재 TD-001은 미구현이므로 수동 생성 경로를 사용할 때는 샘플 `Config/DefaultGame.ini`에 아래 수기 등록도 필요합니다.

```ini
[UETableDesk.DataTables]
Players=/Game/DataTables/DT_Players.DT_Players
Items=/Game/DataTables/DT_Items.DT_Items
```

에디터를 재시작한 뒤 Play합니다. **수기 INI 구역과 툴 자동 등록 구역을 중복으로 두지 마세요.**
나중에 자동 반영으로 전환할 때는 여기서 직접 추가한 수기 구역만 제거하고 툴을 사용합니다. 관리 중인 마커/manifest를 임의로 고치지는 않습니다.
</details>

이 샘플 추가는 TD-001 구현이나 Unreal 실행 검증 완료를 뜻하지 않습니다. UHT/컴파일·PIE·에셋 생성·BP·패키징은 실제 엔진에서 확인해야 합니다.
`Source`, `Config`, 엑셀, JSON, manifest 및 추후 실제 생성·검증한 `.uasset`/`.umap`은 Git으로 관리하고,
`Binaries`, `Intermediate`, `Saved`, `DerivedDataCache`, IDE 파일은 제외합니다. 샘플 전체를 변환기 EXE에 넣지 않고 **템플릿 엑셀만 번들**합니다.

구성 참고: [엔진 연결](https://dev.epicgames.com/documentation/en-us/unreal-engine/managing-game-code-in-unreal-engine),
[빌드 타깃](https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-build-tool-target-reference),
[에디터 Python](https://dev.epicgames.com/documentation/en-us/unreal-engine/scripting-the-unreal-editor-using-python),
[화면 메시지](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Runtime/Engine/UEngine/AddOnScreenDebugMessage).

## 파일 보호·업데이트·Git

생성 파일과 `.tabledesk-manifest.json`을 함께 관리하세요. 수기 파일·이름 충돌·외부 수정은 덮어쓰지 않습니다.
충돌을 무시하려고 manifest를 지우거나 해시를 고치지 마세요. 경로 설정 변경은 기존 파일의 이동·삭제가 아닙니다.
백업은 프로젝트 `Saved/TableDesk` 아래에 보관하며 다중 파일의 완전한 원자성은 보장하지 않습니다.

**기존 게임 프로젝트는 이번 샘플 추가 때문에 재변환·재빌드할 필요가 없습니다.** 새 샘플 프로젝트의 최초 빌드는 별도입니다.
v0.2.0에서 오면 `Find/TryGet` 호출을 Getter 방식으로 직접 교체하고, 행 헤더를 명시적으로 include한 뒤 전체 빌드하세요.
v0.1.x에서 오면 BP 필드가 읽기 전용으로 바뀌므로 기존 쓰기 노드도 점검하세요.
이전 `Public/Data/Generated` 경로의 헤더를 옮길 때는 백업·에디터 종료 후 manifest와 함께 옮기고 include를 갱신해야 합니다.
기존 파일이 있는 대상에는 덮어쓰지 마세요. 되돌릴 때도 생성 파일과 manifest를 같은 시점의 커밋/백업에서 함께 복원합니다.
상세 구버전 이관 기록은 기존 Git 커밋에 남아 있습니다.

이 ZIP에는 기존 `.git` 이력이 포함돼 있습니다. **새 폴더에 압축을 풀어 Git Extensions에서 여세요.**
이미 작업 중인 저장소에는 `.git`을 덮어쓰지 말고 필요한 파일 변경만 비교해 반영하세요. 이번 정리는 원격 업로드 작업이 아닙니다.

도구 저장소에는 앱·샘플·테스트를, 게임 저장소에는 팀 엑셀·생성 코드/JSON/에셋·manifest·필요한 INI 변경을 관리합니다.
로컬 프로젝트 목록은 `%LOCALAPPDATA%/UETableDesk/projects.json`에 저장되며 `TABLEDESK_HOME`으로 변경할 수 있습니다.
이 설정은 아직 팀 공용으로 동기화되지 않습니다. 개인 경로·로그·백업은 커밋하지 마세요.
생성물은 바이트 해시로 보호하므로 Git 줄바꿈 변환에도 주의해야 합니다. 기존 파일을 일괄 정규화하지 마세요.

## 다음 작업

| 순서 | 작업 | 완료 기준 |
|---|---|---|
| **1 · TD-001** | 예정 경로 등록을 에셋 생성과 분리 | `.uasset` 없이 코드/JSON/INI/manifest 생성, 빌드 후 수동 생성한 에셋도 Subsystem 코드 수정 없이 로드 |
| 2 · TD-002 | 실제 Unreal 검증 | UHT/C++·BP 타입 연결·에셋 생성/갱신·Getter·레벨 이동·실패 경로 확인 |
| 3 · TD-003/004/006 | 반영·배포 검증 | 이름이 같은 타입 변경 검출, Reimport 정보 확인, Windows EXE 실행, 패키징 게임에서 테이블 로드 |
| 4 · TD-005/007 | 협업·실패 처리 | 팀 공용 상대 경로 설정, 다른 clone의 해시 호환, 에디터 동시 실행과 부분 저장 실패 처리 |
| 보류 · TD-008/009 | 삭제/이동·타입 확장 | 실제 수요가 생긴 뒤 참조 이관·복구·검증 정책과 함께 결정 |

TD 번호는 내부 작업 표기이며 GitHub Issue가 등록됐다는 뜻은 아닙니다.
**TD-001은 아직 미구현**입니다. 예정 등록과 에셋 준비 완료를 구분하고, INI 변경을 미리 보여준 뒤 적용해야 합니다.
미선택 테이블·수기 설정·인코딩/줄바꿈을 보존하고, 외부 변경 시 중단하며 구버전 이관/복구를 테스트해야 합니다.
같은 내용을 다시 쓰지 않고, 잘못된 Row Struct나 누락 에셋은 null과 진단으로 처리하는 조건도 유지합니다.
별도 명세·로드맵 파일을 다시 늘리지 말고, 세부 작업은 실제 Issue/PR이 생기면 그곳에서 관리합니다.

## 검증

```powershell
python -m unittest discover -s tests -v
python main.py --validate Samples/TableDeskSample/Excel/TableTemplate.xlsx
python -m compileall -q main.py tabledesk tests scripts
python scripts/gui_smoke.py  # 디스플레이 필요; Linux headless는 xvfb-run -a 사용
```

샘플 추가 후 **Python 자동 테스트 152개**, 샘플 등록·재변환 no-op·데이터 변경·등록 미리보기 검사,
Linux GUI smoke 및 실제 샘플 프로젝트의 GUI 등록/전체 코드 미리보기/템플릿 내보내기 검사를 통과했습니다.
C++ 예시 파일은 실제 생성기로 출력하며, 테스트는 텍스트/파일 일치 검증이지 UHT·컴파일 검증이 아닙니다.
Python 테스트와 실제 Unreal 검증은 별개입니다. Windows·UHT/C++·BP·런타임·에셋·쿠킹은 아직 미검증입니다.
[CI 설정](.github/workflows/ci.yml)은 유지하며 GitHub에서의 실제 실행 결과는 별도 확인해야 합니다.
변경 이력은 Git으로 관리하고 별도 CHANGELOG/검증 보고서는 추가하지 않습니다.

라이선스는 [MIT](LICENSE.txt)입니다.
