# UE TableDesk · 0.2.2 프로토타입

> 저장소 전환 정리(2026-10-10): 전체 설계/현재 상태는 [README](README.md), [통합 명세](docs/PROJECT_SPEC.md), [작업 목록](docs/ROADMAP.md)를 참고하세요. 이 문서는 v0.2.2의 현재 사용법입니다. **예정 에셋 경로 사전 등록은 아직 미구현**이며, 아래의 에셋 전체 성공 후 INI 등록이 현재 동작입니다.


**엑셀 → 검증 → JSON / BP 읽기 전용 행 필드 / 테이블 Getter 서브시스템 코드 생성 → 선택적 에셋 반영·자동 등록**

여러 언리얼 프로젝트를 등록해서 사용하는 공용 데스크톱 도구입니다. 도구 실행파일을 각 프로젝트 안에 복사하지 않습니다. 프로젝트를 연 뒤 루트는 고정하고, 생성할 파일의 하위 경로만 설정합니다.

이 배포본은 **Python 소스 + 실행 배치 파일**입니다. Windows용 `.exe`가 미리 빌드되어 있는 배포본은 아닙니다.

## 1. 바로 실행하기

**필요 환경: Python 3.10 이상 + Tkinter. 앱 실행용 pip 패키지는 없습니다.** Windows용 Python 설치에서 Tcl/Tk 구성요소를 포함하세요. Excel 프로그램 자체는 파일을 읽는 데 필요하지 않습니다.

1. ZIP을 원하는 폴더에 전부 압축 해제합니다.
2. `run.bat`을 더블클릭합니다. 또는 터미널에서 `python main.py`를 실행합니다.
3. 첫 화면에서 **샘플로 둘러보기**를 누르면 실제 프로젝트를 건드리지 않고 시험할 수 있습니다. `run_demo.bat`도 같은 기능입니다.

샘플 프로젝트는 앱 사용자 설정 폴더 안에 생성되는 **변환 테스트용 모형**입니다. 언리얼에서 열거나 빌드할 수 있는 실제 프로젝트가 아니며, 이 모형에서는 에셋 실행을 차단합니다. 샘플 원본은 `examples/TableTemplate.xlsx`입니다.

### 실제 프로젝트로 사용하기

`프로젝트 추가` → `.uproject`가 들어 있는 프로젝트 폴더 선택 → `프로젝트 설정` → `엑셀 불러오기` → 테이블 선택 → `선택 항목 변환` → 변경점 확인 → 파일 생성.

프로젝트가 여러 개면 첫 화면에서 전환합니다. **등록 해제는 프로그램의 연결 목록만 제거합니다. 실제 프로젝트나 생성 파일은 삭제하지 않습니다.**

### 미리보기: 개별 데이터와 공통 코드를 분리했습니다

| 화면 | 표시 범위 |
|---|---|
| **테이블 데이터 · 개별 → 데이터 / `<테이블명>.json`** | 목록에서 현재 선택한 테이블 하나. 여러 개를 선택하면 포커스가 있는 테이블을 표시 |
| **프로젝트 코드 · 전체 → `<접두사>StructTypes.h`** | include와 파일 머리말부터 모든 행 구조체까지 한 헤더 전체 |
| **프로젝트 코드 · 전체 → `DataTableSubsystem.h`** | 전체 테이블의 멤버·Getter가 들어 있는 공통 헤더 전체 |
| **프로젝트 코드 · 전체 → `DataTableSubsystem.cpp`** | 공통 로더와 모든 테이블의 초기화·정리 코드 전체 |

프로젝트 코드 화면에서는 테이블 목록을 숨겨 코드 읽기 공간을 확보합니다. 코드 파일이 테이블별로 따로 생성되는 것이 아닙니다.
**정상적으로 불러온 모든 테이블 + 기존에 생성해 관리 중인 테이블**을 합친 결과를 미리 보여줍니다.
테이블 선택/선택 해제를 바꿔도 코드 범위는 바뀌지 않습니다. 엑셀 목록을 비워도 기존 생성 이력이 있으면 그 테이블의 코드가 보존되어 표시됩니다.
오류 테이블은 제외했다고 표시하며, 이미 생성한 테이블의 입력에 오류가 있으면 마지막 생성 스키마를 보존합니다.
원본 읽기 오류가 있으면 화면에 경고하고 실제 변환은 기존과 같이 차단합니다.

파일명 탭, 프로젝트 내 출력 경로, 포함 테이블 목록을 함께 표시합니다. **파일 전체 복사**는 현재 파일의 코드만 복사하며 경로 안내를 코드에 붙이지 않습니다.
C++ 미리보기는 행 수를 제한하지 않습니다. 개별 데이터/JSON 화면의 200행 표시 제한은 그대로입니다.
**새로 고침**은 코드 미리보기를 재계산하는 기능입니다. 엑셀을 수정한 뒤에는 **다시 읽기 / 검증**으로 입력부터 다시 읽으세요.
미리보기와 복사는 프로젝트 파일을 생성·수정하지 않습니다. 파일 충돌이나 외부 수정 때문에 미리보기가 실패하면 이전 화면을 지우고 오류를 표시합니다.

**변환 대상은 여전히 [테이블 데이터]에서 선택한 항목입니다.** 변환 버튼에 선택 개수를 표시합니다.
프로젝트 공통 미리보기는 모든 정상 입력을 합친 예상 결과이고, 선택 변환의 최종 확인 창에서는
**선택한 입력 + 기존에 생성한 테이블**로 구성된 실제 저장 결과를 `생성 코드 전체` 탭에서 다시 보여줍니다.
예를 들어 처음 Players/Items를 불러와 Players만 변환하면 공통 미리보기는 두 테이블을 보여주지만,
최종 확인 창과 실제 생성 파일에는 Players만 포함됩니다. 이미 생성돼 있던 Items는 선택하지 않아도 보존됩니다.

### v0.2.1에서 v0.2.2로 업데이트

기존 앱을 종료하고 새 ZIP을 별도 폴더에 전부 압축 해제해 실행합니다. 등록한 프로젝트·접두사·출력 경로는 그대로 유지합니다.
**이번 변경은 미리보기 UI/범위 정리이며 생성 C++·JSON·UE 등록 동작은 바꾸지 않았습니다.**
`generator_revision=3`을 유지합니다. 동일한 입력과 설정을 사용하는 v0.2.1 프로젝트는 변경 작업이 없으며,
이번 앱 업데이트만을 이유로 재변환·C++ 재빌드·에셋 재임포트를 할 필요는 없습니다.
v0.2.0 이하에서 오는 경우에는 아래의 기존 코드 이관 안내를 적용하세요.

## 2. 프로젝트 설정

| 항목 | 예시 | 기준 |
|---|---|---|
| 프로젝트 루트 | `D:\Dev\OperationBreakpoint` | 등록 시 결정, 작업 화면에서 변경 불가 |
| 대상 모듈 | `OperationBreakpoint` | `Source/<모듈>/<모듈>.Build.cs`가 있는 프로젝트 모듈 |
| 코드 접두사 | `OB` | `OBStructTypes.h`, `FOBPlayersRow`에 적용 |
| 헤더 하위 경로 | `Data` | `Source/<모듈>/Public` 아래 |
| JSON 기본 폴더 | `DataTable` | 프로젝트 루트 아래 |
| 에셋 하위 경로 | `DataTables` | `Content` 아래, UE에서는 `/Game/DataTables` |
| UE 실행파일 | `.../Engine/Binaries/Win64/UnrealEditor-Cmd.exe` | 에셋 반영을 사용할 때만 필요 |

모듈의 `.Build.cs`에는 생성 헤더가 의존하는 `Core`, `CoreUObject`, `Engine` 의존성이 적절히 선언되어 있어야 합니다. 이 도구는 `.Build.cs`, `.uproject`, 소스 관리 설정을 자동 수정하지 않습니다. 별도 UE 에셋 반영이 모두 성공하면 `Config/DefaultGame.ini`의 TableDesk 전용 등록 구역만 생성·갱신합니다. 쿠킹 설정은 자동 변경하지 않습니다.

**기본적으로 추가 하위 경로는 빈 값**이며 다음과 같이 바로 출력합니다.

```text
[프로젝트]/Source/OperationBreakpoint/Public/Data/OBStructTypes.h
[프로젝트]/Source/OperationBreakpoint/Public/Data/DataTableSubsystem.h
[프로젝트]/Source/OperationBreakpoint/Private/Data/DataTableSubsystem.cpp
[프로젝트]/DataTable/Players.json
[프로젝트]/DataTable/Items.json
[프로젝트]/Content/DataTables/DT_Players.uasset  ← 별도 UE 실행 시에만
```

절대 경로, 상위 폴더 이동(`..`), 허용 영역 밖을 가리키는 링크를 차단합니다. 헤더/에셋 폴더는 영문·숫자·밑줄로 구성합니다. 원본 엑셀은 프로젝트 외부에 있어도 됩니다.

제공하는 엑셀의 E1(`SubPath` 값)은 빈 칸입니다. 테이블명이나 시트명으로 하위 폴더를 자동 생성하지 않습니다.
폴더를 나눌 때만 사용자가 E1 또는 앱에서 직접 지정합니다. 예: `Characters`를 지정한 Players → `DataTable/Characters/Players.json`.
빈 값은 입력하지 않은 상태이며 `Null`, `None`, `(없음)` 같은 문자를 경로로 직접 입력하지 않습니다. UI의 `(없음)`은 빈 값의 표시일 뿐입니다.

테이블별 추가 경로는 사용자가 입력한 엑셀 E1의 `SubPath` 값을 기본으로 사용합니다. 앱의 **선택 테이블 경로 지정**에서 값을 저장하면 그 설정이 우선합니다. 빈 칸으로 저장하면 프로젝트 기본 폴더에 바로 출력합니다. 설정 변경은 기존 파일/타입/에셋의 자동 이동이나 삭제가 아닙니다.

### v0.2.0에서 업데이트할 때 (v0.2.1에서 도입한 API 이관)

기존 앱과 언리얼 에디터를 종료하고 새 ZIP을 **새 폴더에 전부 압축 해제**한 뒤 `run.bat`을 실행합니다.
프로젝트를 다시 등록할 필요는 없습니다. 로컬 프로젝트 목록·경로 설정을 그대로 사용합니다.
기존 프로젝트에서 엑셀을 다시 불러와 변환하면 변경점에 다음 이관 안내가 표시됩니다.

- `DataTableSubsystem.h/.cpp`를 **private 테이블 + public `Get<Table>Table()`** 형태로 교체합니다.
- `Find<Table>Row()`와 `TryGet<Table>Row()`는 제거합니다. 호환 래퍼를 추가하지 않습니다.
- 자체 로드 템플릿은 `LoadRegisteredTable(TableName, ExpectedRowStruct)` 일반 함수로 교체합니다.
- 일부 테이블만 선택해도 모든 관리 테이블의 서브시스템 API가 함께 전환됩니다. 미선택 테이블은 삭제하지 않습니다.
- 입력·경로가 같으면 행 구조체 헤더, JSON, 기존 에셋과 등록된 INI는 변경하지 않습니다. 생성 이력의 리비전/코드 해시만 함께 갱신합니다.
- 기존 두 파일과 생성 이력을 백업합니다. 외부 수기 수정·누락 파일·이름 충돌은 기존처럼 차단합니다.

**기존 코드/노드를 이미 사용했다면 연결을 직접 변경해야 합니다.**
C++는 `GetPlayersTable()` 후 `FindRow<FOBPlayersRow>()`, BP는 `Get Players Table` 후 엔진의 `Get Data Table Row`를 사용합니다.
`DataTableSubsystem.h`는 더 이상 `OBStructTypes.h`를 포함하지 않습니다. **행 타입을 사용하는 호출 파일에 `#include "Data/OBStructTypes.h"`를 직접 추가**하세요. 설정한 Public 하위 경로가 다르면 include도 해당 경로를 사용합니다.

Getter는 **공유 원본 UDataTable 객체**를 반환합니다. 이전처럼 읽기 전용 행 포인터/복사본으로 원본을 가두는 API가 아닙니다.
멤버 교체는 private으로 막지만, 반환받은 테이블의 내용 변경은 막지 않습니다. 원본 변경 금지 규칙은 호출 측에서 지킵니다.
로드 실패 시 Getter는 `nullptr`를 반환하므로 호출 측에서 유효성·행 조회 실패를 처리하세요.

C++ 사용처를 고친 뒤 **Editor 타깃 전체 빌드 → 에디터 실행 → 기존 BP 노드 재연결·컴파일** 순서로 확인합니다.
기존 에셋·등록 경로·행 스키마가 같으면 이 API 이관만을 이유로 에셋을 다시 임포트할 필요는 없습니다.
미리보기의 파일 목록과 C++ diff를 확인한 뒤 적용하세요. 앱은 다른 클래스나 BP 에셋을 자동 편집하지 않습니다.

새 생성 이력은 `generator_revision=3`이며 v0.2.0 앱의 변환은 차단됩니다. 앱 소스 일부를 구버전과 섞거나 이전 앱으로 되돌려 변환하지 마세요.
되돌리려면 앱·프로젝트 코드를 이전 버전으로 맞추고 변경한 파일과 `.tabledesk-manifest.json`을 **동일 시점의 백업/커밋에서 함께 복원**하세요.

### v0.1.x에서 바로 업데이트할 때

같은 실행 절차를 사용합니다. 기존 생성 이력을 읽어 서브시스템 두 파일을 새로 만들고, 관리 중인 모든 행 필드에서
`EditAnywhere, BlueprintReadWrite`를 `BlueprintReadOnly`로 전환하며 `Category`를 유지합니다.
미선택 JSON·사용자 경로는 보존하고, 기존 생성 파일과 이력을 백업합니다.
읽기 전용 전환으로 기존 BP 쓰기 노드가 깨질 수 있으므로 Editor 전체 빌드와 BP 컴파일을 확인하세요.
수기 수정 파일은 자동 덮어쓰지 않습니다. `UDataTableSubsystem`은 프로젝트당 하나이며 접두사를 바꿔 두 번째 클래스를 만드는 용도가 아닙니다.

### v0.1.0의 이전 경로를 정리할 때

앱을 종료하고 새 배포본을 압축 해제해 `run.bat`을 실행합니다. 등록 목록은 기존 로컬 설정에서 읽습니다.
기존 프로젝트에 저장된 경로는 **업데이트만으로 강제 변경하지 않습니다.**

기존 프로젝트를 열고 엑셀을 불러온 다음 **프로젝트 설정 → 기본 경로 적용 → 설정 저장**을 누르면 됩니다.
헤더 하위 경로는 `Data`, JSON 기본 폴더는 `DataTable`로 바뀌며, 현재 불러온 테이블과 저장된 경로 설정의 추가 하위 경로는 모두 빈 값으로 저장됩니다.
이때 접두사·대상 모듈·프로젝트 루트·에셋 기본 폴더·엑셀 원본은 변경하지 않습니다. `취소`하면 설정 변경을 폐기합니다.
이전 템플릿의 E1에 `Characters`/`Items`가 남아 있어도 저장한 빈 경로가 우선합니다.
나중에 처음 불러오는 다른 테이블의 E1에 경로가 있으면 그 값은 사용자 지정 경로로 적용됩니다.

개별 테이블만 초기화할 때는 **선택 테이블 경로 지정 → 비우기 → 저장**을 사용합니다.

**이미 변환하여 파일을 생성했다면:** 이 버튼은 설정 변경이지 파일 이동 기능이 아닙니다.
기존 `Public/Data/Generated/OBStructTypes.h`가 있으면 새 경로에 같은 이름의 헤더를 중복 생성하지 않고 중단합니다.
새 경로로 실제 이전하려면 프로젝트를 백업하고 에디터를 종료한 상태에서 기존 헤더와 옆의 `.tabledesk-manifest.json`을 **함께** `Public/Data`로 옮기세요.
대상에 기존 파일이 있으면 덮어쓰지 말고 충돌을 먼저 확인하세요. `Data/Generated/...`를 사용하는 C++ include가 있다면 별도로 갱신하고 다시 빌드해야 합니다.
예전 JSON/에셋은 자동 삭제·이동하지 않으며, 새 출력 위치의 JSON은 다음 변환에서 생성합니다.
아직 변경점 미리보기만 확인했고 파일 생성은 누르지 않았다면 이 이전 작업은 필요 없습니다.

## 3. 엑셀 작성 규격

**시트 1개 = 테이블 1개.** 파일 여러 개를 한 번에 불러올 수 있습니다. 설명용 시트는 이름을 `_`로 시작하세요. 예: `_Guide`.

| 행 | A | B | C | D | E |
|---|---|---|---|---|---|
| 1 | TableName | Players | 비워 둠 | SubPath | 비워 둠 |
| 2 | RowName | RawName | Name | ID | ... |
| 3 | RowKey | String | Name | Int | ... |
| 4부터 | Player_001 | 기본 플레이어 | DefaultPlayer | 1 | ... |

**1행 메타데이터와 2~3행 컬럼 정의는 서로 독립적입니다.** E1은 추가 하위 경로이며, E2부터는 다섯 번째 데이터 컬럼입니다. D1/E1의 SubPath는 생략할 수 있습니다. 나머지 컬럼은 필요한 만큼 오른쪽에 추가하세요.

지원 타입:

| 엑셀 타입 | C++ 출력 | 비어 있을 때 |
|---|---|---|
| RowKey | 일반 멤버로 만들지 않음 | 오류 |
| String / FString | FString | 빈 문자열 |
| Name / FName | FName | `None` / NAME_None |
| Int / int32 | int32 | 오류 |
| Float | float | 오류 |
| Bool | bool | 오류 |

타입 이름은 대소문자를 구분하지 않습니다. Bool은 TRUE/FALSE, 1/0을 사용할 수 있습니다. String/Name/행 키는 **텍스트 셀**로 입력합니다. 숫자처럼 보이는 문자열도 텍스트로 저장해 앞자리 0을 보존하세요.

첫 컬럼은 반드시 `RowName / RowKey`입니다. `RawName`은 자동으로 RowName으로 바꾸지 않는 일반 문자열 필드입니다. UE 에셋 반영에서는 `ImportKeyField = RowName`으로 설정하므로, 일반 데이터 필드 `Name`도 사용할 수 있습니다.

필드/테이블명은 영문으로 시작하고 영문·숫자·밑줄만 사용합니다. C++ 예약어와 일부 엔진 예약 이름은 금지합니다. 행 키는 영문·숫자·밑줄·하이픈으로 1~128자이며 `None`은 사용할 수 없습니다. 행 키와 필드명 중복은 대소문자를 구분하지 않고 검사합니다.

**수식, 날짜/시간, 병합 셀, Excel 오류, `.xls`/`.xlsm`, 배열, Enum, FText, Struct 중첩, 에셋 참조는 지원하지 않습니다.** 수식 계산값이 필요하면 복사 후 '값으로 붙여넣기' 하세요. 계산 캐시를 임의로 믿고 변환하지 않습니다. 빈 테이블로 기존 데이터를 지우는 작업도 차단합니다.

파일 크기 32 MiB, 압축 해제 합계 96 MiB, 워크시트 XML 하나 32 MiB, 비어 있지 않은 셀 합계 250,000개, 테이블 최대 50,000 데이터 행/128열을 제한합니다. UI 미리보기는 최대 200행이며 JSON에는 검증된 전체 행을 저장합니다. 이 한계치는 지원 상한선이지 대용량 성능 보장이 아닙니다.

엑셀을 수정·저장했다면 **다시 읽기 / 검증**을 누르세요. 불러오기나 변경점 미리보기 이후 원본이 바뀌면 해시를 비교해 낡은 데이터의 변환을 차단합니다.

## 4. 헤더 생성과 파일 보호

```cpp
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
};
```

- `OBStructTypes.generated.h`는 include만 작성합니다. 실제 generated.h는 UHT가 생성하며 이 도구는 만들지 않습니다.
- **수기 헤더/서브시스템은 자동 수정하지 않습니다.** 기존 이름과 충돌하면 중단합니다. 프로젝트당 고정 서브시스템 하나를 사용하므로 접두사 변경만으로 중복 클래스를 만들지 않습니다.
- Source 아래에 같은 이름의 헤더가 다른 경로에 있으면 중복 생성을 차단합니다.
- TableDesk가 만든 헤더는 테이블별 BEGIN/END 마커 구간을 갱신하며 선택하지 않은 구조체와 구간 바깥 코드는 유지합니다.
- 생성 구간을 외부에서 수정했거나 기존 JSON이 변경됐으면 덮어쓰기를 차단합니다. 실수로 수기 변경을 덮는 것을 방지하는 기능이며, 병합 도구는 아닙니다.
- 데이터 값/행만 바뀌면 JSON·생성 이력을 갱신하고 동일한 C++ 파일 3개는 다시 쓰지 않습니다. 코드 변경은 **C++ 변경점** 탭에서 .h/.cpp 전체 diff로 확인합니다.
- 미리보기 이후 생성 대상 파일이 바뀌면 저장을 중단합니다.
- 변경될 기존 파일은 `Saved/TableDesk/Backups/<실행시각>/`에 먼저 백업합니다. 저장 오류 시 이미 적용한 파일의 복원을 시도합니다. 전원 차단까지 보장하는 다중 파일 트랜잭션은 아닙니다.

헤더 옆의 `.tabledesk-manifest.json`은 생성 이력/소유권 해시입니다. **이 파일을 생성한 .h/.cpp와 함께 유지하고 소스 관리에 포함하세요.** 선택 해제, 원본 파일 목록 비우기, 프로젝트 등록 해제는 생성물을 자동 삭제하지 않습니다.

필드 삭제/타입 변경/행 키 변경은 게임 C++ 코드나 Blueprint/DataTableRowHandle 참조를 자동 이관하지 않습니다. 개발자가 검토해야 합니다. 접두사/모듈/헤더 경로 변경은 기존 타입의 자동 이름 변경·이전 작업이 아닙니다. 기존 생성물이 있으면 충돌 검토/수동 이전이 필요합니다.

### 4.1 `UDataTableSubsystem` 생성 규칙

클래스명은 **`UDataTableSubsystem : public UGameInstanceSubsystem`으로 고정**합니다. 파일명에도 프로젝트 접두사를 붙이지 않습니다.
접두사는 행 타입·행 헤더에만 적용하고, API 매크로는 대상 모듈명에서 생성합니다.
`.h`는 행 헤더와 같은 Public 하위 경로, `.cpp`는 대응하는 Private 하위 경로에 생성합니다. 기본값은 각각 `Public/Data`, `Private/Data`입니다.

```cpp
public:
    UFUNCTION(BlueprintPure, Category = "DataTable")
    UDataTable* GetPlayersTable() const
    {
        return PlayersTable.Get();
    }

private:
    UPROPERTY(Transient)
    TObjectPtr<UDataTable> PlayersTable = nullptr;
```

테이블마다 **private 멤버 하나와 C++/BP 공용 Getter 하나**를 생성합니다. Getter는 헤더에 직접 정의합니다.
런타임 `TMap`, 별도의 `Find/TryGet` 행 조회 래퍼, Setter, 자체 로드 템플릿은 생성하지 않습니다.
내부 `UPROPERTY(Transient)`와 행 필드의 `BlueprintReadOnly + Category`는 서로 다른 용도입니다. 추가 `meta` 설정 UI는 없습니다.

`Initialize()`의 테이블별 코드는 다음처럼 생성합니다.

```cpp
PlayersTable = LoadRegisteredTable(TEXT("Players"), FOBPlayersRow::StaticStruct());
```

공통 로더는 `.cpp` 안의 일반 함수 하나입니다.

```cpp
UDataTable* LoadRegisteredTable(const TCHAR* TableName, const UScriptStruct* ExpectedRowStruct);
```

이 함수는 기존 INI에서 에셋 경로를 읽어 동기 로드하고, 기대한 행 구조체 타입과 비교합니다.
**엔진 제공 API인 `LoadObject<UDataTable>`는 그대로 사용**합니다. 제거한 것은 생성기 자체의 `template <typename TRow>` 로더입니다.

- 등록 누락·로드 실패·잘못된 행 구조체는 초기화 로그를 남기고 `nullptr`로 처리합니다. 자동 재시도는 없습니다.
- Getter는 저장된 포인터만 반환합니다. 로드·행 조회·복사·타입 변환을 Getter 안에서 수행하지 않습니다.
- `Deinitialize()`에서 각 테이블 멤버를 `nullptr`로 정리합니다. Tick, 레벨마다 재로드, 싱글턴 static 인스턴스는 생성하지 않습니다.
- 새 테이블을 추가하면 기존 멤버를 유지하면서 멤버·Getter·초기화·정리 코드만 추가합니다.
- 값만 바꾸면 모든 C++ 파일은 그대로입니다. 기존 행의 필드만 바꾸면 행 헤더는 갱신하지만, 테이블명·include 경로가 같을 때 서브시스템 h/cpp는 다시 쓰지 않습니다.

**읽기 전용 보호 범위가 v0.2.0과 다릅니다.** Getter 반환값은 복사본이 아닌 공유 UDataTable입니다.
`const` 멤버 함수/`BlueprintPure`는 반환된 객체 전체를 불변으로 만들지 않습니다. 테이블 변수 자체는 private이지만 원본 내용 변경까지 막지는 않습니다.
데이터 원본은 엑셀에서 관리하고, 플레이 중 변하는 상태는 캐릭터/컴포넌트 등 호출 측의 값으로 분리하세요.
호출은 게임 스레드에서 수행하고, 작업 스레드에는 필요한 행 데이터를 복사해 전달하세요. Getter 자체에 스레드 검사를 넣지는 않습니다.

서브시스템 헤더는 `Engine/DataTable.h`를 포함하고 **행 헤더는 `.cpp`에서만 포함**합니다.
C++ 호출 측에서 `FOBPlayersRow`를 사용할 때는 해당 행 헤더를 명시적으로 include해야 합니다.

관리 중인 서브시스템 두 파일은 **전체 자동 생성 전용**입니다. 수기 편집은 해시 검사로 차단합니다. 사용자 로직은 호출 측/별도 클래스에 두세요.
클래스/파일 충돌은 프로젝트 Source와 프로젝트 Plugins를 검사합니다. 엔진에 설치된 외부 플러그인까지 완전히 검사하는 것은 아니므로 실제 UHT 빌드가 최종 확인입니다.

### 4.2 Blueprint / C++ 사용 흐름

Blueprint에서는 다음 순서로 연결합니다. 실제 노드 생성·실행은 이 환경에서 검증하지 않았으므로 `docs/ENGINE_CHECKLIST.md`의 절차로 확인하세요.

```text
Get Game Instance Subsystem (DataTableSubsystem)
    → Get Players Table
    → Is Valid 확인
    → Get Data Table Row (Row Name = Player_001)
    → Row Found 경로에서 Out Row의 필드 사용
```

**Getter는 UDataTable만 반환하므로 BP 그래프에 행 타입까지 자동 지정하지는 않습니다.**
`Get Data Table Row`의 `Out Row`를 해당 행 구조체 타입의 변수 입력이나 `Break OBPlayersRow`의 구조체 입력에 연결해 타입을 정하세요.
구조체/노드의 표시 이름은 엔진 표시 규칙에 따라 공백 등이 다를 수 있습니다.
`Row Not Found`에서는 성공 출력으로 처리하지 않고 별도 실패 로직으로 분기합니다. 이전 `TryGet`의 출력 기본값 초기화 래퍼는 더 이상 없습니다.

C++ 예시는 다음과 같습니다. 이미 생성된 파일에 넣는 것이 아니라 호출하는 Actor 등의 `.cpp`에 작성합니다.

```cpp
#include "Engine/GameInstance.h"
#include "Data/DataTableSubsystem.h"
#include "Data/OBStructTypes.h"  // Include row types explicitly.

// Inside an Actor method:
UGameInstance* Instance = GetGameInstance();
UDataTableSubsystem* Tables = Instance ? Instance->GetSubsystem<UDataTableSubsystem>() : nullptr;
UDataTable* Players = Tables ? Tables->GetPlayersTable() : nullptr;
if (IsValid(Players))
{
    const FOBPlayersRow* Row = Players->FindRow<FOBPlayersRow>(
        FName(TEXT("Player_001")), TEXT("PlayerInit"), false);
    if (Row)
    {
        const FOBPlayersRow PlayerData = *Row;
        // Initialize runtime state from PlayerData. Do not edit the table.
    }
    else
    {
        // Handle a missing row or mismatched row type.
    }
}
else
{
    // Handle an unavailable subsystem/table.
}
```

반환받은 행 포인터는 재임포트·종료를 넘겨 보관하지 않고, 장기 사용값은 복사하세요.
`examples/expected/`에 현재 버전의 전체 행 헤더와 서브시스템 .h/.cpp가 있습니다.

## 5. UE DataTable 에셋 반영 — 실험 기능

**이 배포본에서 실제 언리얼 런타임 연동, UHT/C++ 빌드, `.uasset` 생성 성공은 검증하지 못했습니다.** 공식 API를 바탕으로 작성한 선택 기능입니다. 실제 프로젝트 복사본과 버전 관리에서 먼저 시험하세요.

앱의 `선택 항목 변환`은 JSON, 행 헤더, 서브시스템 .h/.cpp와 생성 이력만 생성합니다. 이 단계에서는 `DefaultGame.ini`를 변경하지 않습니다. `.uasset`은 다음 별도 단계를 거쳐야 합니다.

1. 프로젝트에서 `Python Editor Script Plugin`과 `Editor Scripting Utilities`를 활성화하고 저장합니다.
2. 생성한 행 헤더와 **서브시스템 .h/.cpp까지 포함하여 C++ Editor 타깃을 전체 빌드**합니다. 이 버전은 자동 빌드/Live Coding을 수행하지 않습니다.
3. 해당 프로젝트를 연 언리얼 에디터를 모두 종료합니다.
4. 앱의 프로젝트 설정에서 **그 프로젝트에 맞는 엔진 버전**의 `UnrealEditor-Cmd.exe`를 지정합니다. 자동 엔진 버전 선택은 하지 않습니다.
5. 테이블을 선택하고 **UE 에셋 반영 (실험)**을 누른 후 확인 내용을 읽고 실행합니다.

앱에 포함된 외부 스크립트를 Python commandlet으로 실행합니다. 프로젝트에 툴 플러그인/실행파일/스크립트를 복사하지 않습니다. 다만 엔진 내장 Python 플러그인 활성화는 프로젝트별로 필요합니다.

엔진 측에서는 먼저 모든 JSON을 임시 DataTable에 넣어 검증하고, 행 키/컬럼을 확인합니다. 새 에셋은 `DataTableFactory`로 생성하고 기존 에셋은 동일 구조체를 사용할 때만 갱신합니다. 이미 다른 종류의 에셋이 있거나 다른 구조체를 사용하는 경우 중단합니다.

기존 `.uasset` 및 관련 파일은 `Saved/TableDesk/AssetBackups/`에 백업합니다. **에셋 저장은 파일별로 순차 실행하므로 중간 실패 시 일부만 반영될 수 있습니다.** 실패 결과에는 저장 완료 목록과 백업 위치를 표시합니다. 자동 전체 롤백을 보장하지 않습니다.

빌드 유효성은 사용자의 확인을 전제로 합니다. 현재 스크립트가 컴파일된 프로퍼티의 모든 타입이나 외부 참조까지 검증하는 것은 아닙니다. 컬럼이 같고 타입만 바뀐 경우도 반드시 전체 빌드하세요. 에디터 실행 여부를 자동으로 감지하거나 강제 종료하지 않습니다.

소스 관리 자동 checkout은 하지 않습니다. 파일이 읽기 전용이면 먼저 직접 checkout하거나 쓰기 권한을 확보하세요. Blueprint 전용 프로젝트, 플러그인 모듈, 네트워크 다중 작성자 동시 편집은 이 버전의 지원 범위가 아닙니다.


### 성공 후 런타임 등록

선택한 에셋이 **모두 저장된 뒤에만** 앱이 `Config/DefaultGame.ini`에 아래 전용 구역을 생성·갱신합니다.
이미 성공한 다른 테이블은 유지하고, 에셋 경로 변경도 해당 테이블의 새 에셋 반영 성공 이후에만 반영합니다.

```ini
; BEGIN TABLEDESK: RUNTIME
; Generated after successful asset import. Do not edit this block.
[UETableDesk.DataTables]
Items=/Game/DataTables/DT_Items.DT_Items
Players=/Game/DataTables/DT_Players.DT_Players
; END TABLEDESK: RUNTIME
```

서브시스템은 다음 게임 실행의 초기화에서 이 등록 경로를 읽습니다. 경로는 C++에 하드코딩하지 않으므로 **동일 테이블의 에셋 위치만 변경하면 C++ 재생성이 필요 없습니다.**
다른 INI 구역/주석/원래 인코딩·줄바꿈은 보존합니다. 수기 등록 구역, 생성 구역 외부 수정, 작업 중 설정 변경은 차단합니다.
등록 설정과 생성 이력은 백업/일반 오류 롤백 대상입니다. 에셋은 저장됐지만 설정 저장이 실패할 수 있으며, 이때는 해당 상태를 별도 오류로 알립니다.

**쿠킹/패키징 규칙은 아직 자동 설정하지 않습니다.** INI의 문자열 경로만으로 쿠킹 포함이 보장된다고 가정하지 마세요.
패키징 설정의 Additional Asset Directories to Cook 또는 프로젝트의 Asset Manager 규칙에 실제 테이블 폴더(기본 `/Game/DataTables`)를 포함하고 패키징 빌드에서도 조회를 확인하세요.
기본형 작은 마스터 테이블의 동기 선로딩만 지원합니다. 무거운 에셋 참조, 비동기 로드, 런타임 리로드, 멀티플레이 복제는 이번 범위가 아닙니다.

## 6. 저장 위치와 협업

프로젝트 등록 정보는 기본적으로 `%LOCALAPPDATA%/UETableDesk/projects.json`에 저장합니다. 비 Windows는 `~/.local/share/UETableDesk`입니다. `TABLEDESK_HOME` 환경변수로 변경할 수 있습니다.

이 설정은 **PC별 로컬 설정**입니다. 팀원 간 설정 자동 동기화나 공유 서버, 접근 권한, 승인 워크플로는 구현하지 않았습니다. 팀 공용 배포는 동일한 앱 폴더를 각자 사용하고 프로젝트를 각각 연결하는 방식입니다.

앱 자체는 원격 서비스에 데이터를 전송하지 않습니다. UE 실행 시에는 해당 프로젝트/엔진의 원래 시작 동작과 플러그인 동작이 적용됩니다.

권장 소스 관리 범위는 엑셀 원본, 생성 .h/.cpp/JSON/에셋, `.tabledesk-manifest.json`, 성공 후 갱신된 `Config/DefaultGame.ini`입니다. `Saved` 백업과 사용자별 앱 설정은 보통 저장소에서 제외합니다.

## 7. 테스트와 선택적 EXE 패키징

```powershell
# GUI 없이 샘플만 검증
python main.py --validate examples/TableTemplate.xlsx

# 변환/입력 검증 테스트
python -m unittest discover -s tests -v

# 실제 GUI smoke test (표시 장치 필요)
python scripts/gui_smoke.py
```

`scripts/gui_smoke.py`는 앱 코드와 표준 라이브러리만으로 실행합니다. 선택적 스크린샷 캡처 옵션을 사용하는 개발자에게만 Pillow가 필요하며, 일반 앱에는 필요 없습니다.

Windows에서 Python이 없는 PC에 전달할 패키지가 필요할 때는:

```powershell
py -3 -m pip install pyinstaller
.\build_windows.bat
```

`dist/UETableDesk/` 폴더 전체를 전달하면 됩니다. 그 안의 exe 하나만 떼어 전달하지 마세요. **이 배포본에서는 Windows 패키징 결과를 만들거나 실행 검증하지 않았습니다.**

## 8. 파일 구성

```text
main.py                    실행 / GUI 없는 검증
run.bat                    Windows 실행
run_demo.bat               샘플 프로젝트로 실행
build_windows.bat          선택적 Windows 패키징
README_KO.md               이 설명서
VALIDATION.md              검증 범위 / 미검증 항목
examples/TableTemplate.xlsx
examples/expected/         샘플 JSON/행 헤더/서브시스템 .h/.cpp (참고용)
tabledesk/core.py           설정, 타입 검증, 경로 보호, 코드 생성, 백업
tabledesk/xlsx_reader.py    읽기 전용 OOXML 리더 (표준 라이브러리)
tabledesk/gui.py            개별 데이터 UI / 프로젝트 공통 파일 UI / 선택 변환 diff
tabledesk/code_preview.py   전체 코드 파일의 읽기 전용 미리보기 모델
tabledesk/subsystem_codegen.py    private 멤버·공용 Getter·일반 로더 코드 생성
tabledesk/runtime_registration.py 성공 이후 등록 설정·생성 이력 갱신
tabledesk/unreal_runner.py  외부 Unreal 실행
tabledesk/unreal_bridge.py  엔진 안에서 실행할 에셋 반영 코드
tests/test_core.py          기존 자동화 테스트
tests/test_defaults.py      기본 경로/빈 추가 경로/기존 설정 회귀 테스트
tests/test_subsystem.py     코드 생성/충돌 방지/v0.1.x 이관 테스트
tests/test_getters.py       Getter API/v0.2.0 생성물 이관 회귀 테스트
tests/test_code_preview.py  전체 범위/정확한 파일 내용/선택 변환/무변경 미리보기
tests/fixtures/v020/        원본 v0.2.0으로 생성한 테스트 입력 (사용 예시 아님)
tests/test_registration.py  INI 소유권/성공 시 등록/복원 테스트
tests/test_runner.py        외부 프로세스 모의 실행·등록 순서 테스트
scripts/gui_smoke.py        실제 UI 시작/입력/변환 테스트
docs/                      실제 실행 화면
```

## 공식 참고 문서

아래는 이전 리비전에서 제공한 공식 참고 문서입니다. v0.2.2는 미리보기 UI 변경이며 엔진 API를 변경하거나 새로 검증하지 않았습니다.
기존 로더/Config 및 Python 에셋 어댑터의 동작을 유지합니다.
기존 Python 에셋 어댑터는 v0.1.x의 UE 5.7 API 기반 실험 코드입니다. 문서 확인은 실제 엔진 실행 검증이 아닙니다.

- Python / Tkinter: https://docs.python.org/3/library/tkinter.html
- UE Python 실행/플러그인: https://dev.epicgames.com/documentation/en-us/unreal-engine/scripting-the-unreal-editor-using-python
- UHT 빌드: https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-header-tool-for-unreal-engine
- DataTableFactory: https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/DataTableFactory?application_version=5.7
- DataTable / ImportKeyField: https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/DataTable?application_version=5.7
- JSON 임포트: https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/DataTableFunctionLibrary?application_version=5.7
- 에셋 생성: https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/AssetTools?application_version=5.7
- 에셋 저장: https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/EditorAssetLibrary?application_version=5.7
- EXE 패키징: https://pyinstaller.org/en/stable/usage.html

- UPROPERTY 지정자: https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-uproperties
- UFUNCTION 지정자: https://dev.epicgames.com/documentation/en-us/unreal-engine/ufunctions-in-unreal-engine
- GameInstanceSubsystem: https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Runtime/Engine/UGameInstanceSubsystem
- Subsystem 사용: https://dev.epicgames.com/documentation/en-us/unreal-engine/programming-subsystems-in-unreal-engine
- FindRow: https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Runtime/Engine/UDataTable/FindRow
- 객체 포인터/GC: https://dev.epicgames.com/documentation/en-us/unreal-engine/object-pointers-in-unreal-engine
- Config/GGameIni: https://dev.epicgames.com/documentation/en-us/unreal-engine/configuration-files-in-unreal-engine
- LoadObject: https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Runtime/CoreUObject/LoadObject
- 쿠킹 설정: https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Developer/DeveloperToolSettings/UProjectPackagingSettings

- UDataTable/GetRowStruct: https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Runtime/Engine/UDataTable
- Get Data Table Row 노드: https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Editor/BlueprintGraph/UK2Node_GetDataTableRow
