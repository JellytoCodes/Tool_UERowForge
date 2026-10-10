# UE TableDesk 통합 명세

정리일: 2026-10-10 · 코드 기준: v0.2.2 / generator revision 3

## 1. 목적과 범위

기획자가 작성한 엑셀을 단일 원본으로 삼아 JSON·C++ 행 구조체·DataTable 관리 코드를 일치시킨다. 여러 프로젝트를 같은 앱에서 전환하고, 개발자가 테이블마다 반복 선언·Getter·로드 코드를 직접 수정하는 일을 줄인다.

엑셀 편집기를 대체하는 웹 협업 서비스가 아니다. Git 클라이언트도 아니다. Git Extensions처럼 **프로젝트 선택 → 해당 프로젝트 작업 화면**으로 진입하는 사용 모델을 참고한다.

| 담당 | 작업 |
|---|---|
| 기획자 | 엑셀 데이터 작성, 검증/변환, 변경 내용 확인 |
| 개발자 | 스키마 변경 검토, Editor 타깃 빌드, 실제 에셋 생성/검증, 게임 사용처 구현 |
| 도구 | 형식 검증, 결정적 코드/JSON 생성, 파일 보호, 선택적인 빌드 후 에셋 처리 |

스키마 자동 생성이 게임 로직 자동 구현을 의미하지 않는다. 예를 들어 필드 이름 변경 시 기존 C++·BP 사용처는 별도 수정이 필요하다.

## 2. 프로젝트 등록과 경로

공용 앱에 프로젝트를 추가하고 `.uproject`가 있는 폴더를 선택한다. 루트가 여러 `.uproject`를 포함하면 대상을 선택한다. 등록 해제는 로컬 연결 설정만 제거한다.

현재 지원 대상은 `Source/<Module>/<Module>.Build.cs`가 있는 프로젝트 C++ 모듈이다. Blueprint-only와 플러그인 모듈 대상 생성은 지원하지 않는다. `Core`, `CoreUObject`, `Engine` 의존성 및 실제 모듈의 API 매크로는 확인해야 한다.

| 설정 | 기본값/규칙 |
|---|---|
| 프로젝트 루트 | 최초 등록 시 선택, 작업 화면에서는 수정 불가 |
| 대상 모듈 | 프로젝트 모듈 목록에서 선택 |
| 접두사 | 사용자 지정. 예: `OB` |
| 행 헤더 | `Source/<Module>/Public/Data/<Prefix>StructTypes.h` |
| Subsystem 헤더 | `Source/<Module>/Public/Data/DataTableSubsystem.h` |
| Subsystem CPP | `Source/<Module>/Private/Data/DataTableSubsystem.cpp` |
| JSON 기본 폴더 | `<Project>/DataTable` |
| 에셋 기본 폴더 | `<Project>/Content/DataTables`, Unreal 경로 `/Game/DataTables` |
| 테이블별 추가 경로 | 빈 값. 필요할 때만 사용자 지정 |

`DataTable`(JSON, 단수)과 `DataTables`(에셋, 복수)는 현재 기본값을 그대로 구분한다. `Player`와 `Players`도 임의로 단수/복수 변환하지 않는다. `Player → DT_Player`, `Players → DT_Players`다.

원본 엑셀은 프로젝트 밖에서 불러올 수 있다. 출력은 프로젝트와 각 기준 폴더 내부로 제한한다. 절대 경로·`..`·범위를 벗어나는 링크·예약 경로를 차단한다.

프로젝트별 설정은 현재 로컬 앱 설정에 저장된다. Windows 기본 위치는 `%LOCALAPPDATA%/UETableDesk`이며 `TABLEDESK_HOME`으로 대체할 수 있다. **팀 공용 프로젝트 설정 파일의 내보내기/가져오기는 아직 없다.** [TD-005](ROADMAP.md)

## 3. 입력 규격

`.xlsx` 파일 여러 개, 시트 하나당 테이블 하나. `_Guide`처럼 `_`로 시작하는 시트는 설명용이다.

| 행 | A | B | C | D | E |
|---|---|---|---|---|---|
| 1 | TableName | Players | 빈 값 | SubPath | 빈 값 |
| 2 | RowName | RawName | Name | ID | ... |
| 3 | RowKey | String | Name | Int | ... |
| 4 이후 | Player_001 | 기본 플레이어 | PlayerBasic | 1 | ... |

`RowName`은 행 식별자이며 구조체 일반 멤버가 아니다. `RawName`은 별도의 문자열 필드다. 일반 필드 `Name`과 행 키가 충돌하지 않도록 UE 임포트 키를 `RowName`으로 지정한다.

현재 지원 타입은 String/FString, Name/FName, Int/int32, Float, Bool이다. 배열·Enum·FText·중첩 구조체·에셋 참조·수식·날짜·병합 셀·xls/xlsm은 지원하지 않는다. 상세 제한값과 입력 오류는 [사용 설명서](../README_KO.md)에 따른다.

앱에서 저장한 테이블 경로는 엑셀의 SubPath보다 우선한다. 빈 값도 명시적인 사용자 설정이며 테이블별 폴더를 자동 생성하지 않는다.

## 4. C++ 출력 규칙

### 행 구조체

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

`<Module>_API`는 실제 대상 모듈 이름에 맞춘다. `<Prefix>StructTypes.generated.h`는 마지막 include이며 도구가 직접 파일을 만들지 않는다. UHT가 생성한다. [Epic UHT](https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-header-tool-for-unreal-engine)

BP 사용 때문에 `BlueprintReadOnly`를 유지한다. 편집/쓰기 지정자와 추가 meta 설정은 생성하지 않는다. Category는 테이블명이다. 기존 수기 헤더를 찾아 임의 편집하는 기능은 없다.

### 관리 서브시스템

클래스명은 `UDataTableSubsystem : public UGameInstanceSubsystem`으로 고정한다. 접두사 변경으로 여러 관리 클래스를 만드는 기능이 아니다.

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

테이블이 추가될 때 private 포인터, public Getter, 초기화/정리 코드가 함께 추가된다. TMap 기반 저장·행 조회 래퍼·자체 로드 템플릿은 사용하지 않는다.

공통 로더는 `.cpp` 내부의 `LoadRegisteredTable(const TCHAR*, const UScriptStruct*)`다. GConfig 경로 읽기 → `LoadObject<UDataTable>` → RowStruct 일치 확인 → 멤버 보관 순서다. 초기화 시 동기 로드하고 종료 시 참조를 정리한다. 에셋이 없거나 타입이 다르면 nullptr로 유지하고 로그를 남긴다.

Subsystem `.h`는 행 헤더를 포함하지 않는다. 행 타입을 사용하는 C++ 파일에서 해당 행 헤더를 명시적으로 include한다. BP에서는 Getter에서 얻은 DataTable을 엔진의 행 조회 노드에 연결한다. **동적 DataTable 핀에서 출력 행 타입을 지정하는 실제 사용성은 UE에서 검증해야 한다.**

읽기 전용 필드 지정은 C++ 불변성 보장이 아니다. Getter는 공유 원본 테이블이며 호출 측은 null/행 없음 처리와 원본 변경 금지 규칙을 지킨다. 마스터 기본값과 현재 체력 같은 런타임 상태는 분리한다.

## 5. 미리보기와 저장 범위

| 화면 | 범위 |
|---|---|
| 데이터/JSON | 현재 포커스 테이블 하나 |
| 프로젝트 코드 | 모든 정상 입력 + 기존 생성 이력의 보존 테이블, C++ 세 파일 전체 |
| 선택 변환 직전 확인 | 이번 선택 입력 + 기존 보존 테이블, 실제 저장될 파일 전체 |

테이블 선택 변경이 공통 코드 파일을 개별 코드처럼 보이게 만들면 안 된다. 미리보기와 복사는 읽기 전용이다. 기존 테이블은 이번 선택에서 빠졌다는 이유만으로 삭제하지 않는다.

데이터 값만 바뀌면 동일한 C++는 다시 쓰지 않는다. 파일 전체 비교/해시로 불필요한 저장을 피한다.

## 6. 에셋 생성·등록·빌드의 분리

### 현재 구현

```text
선택 변환 → JSON + C++ + manifest 생성
                   ↓ 개발자가 Editor 타깃 빌드
UE 에셋 반영(실험) → 임시 DataTable 검증 → 신규 생성/기존 갱신 → 저장
                   ↓ 선택 에셋 전체 성공
DefaultGame.ini의 전용 등록 구역 갱신
                   ↓ 게임 시작
Subsystem이 경로를 읽고 로드
```

현재 일반 변환 버튼은 `DefaultGame.ini`를 쓰지 않는다. `.uasset`이 없더라도 manifest에는 예정 에셋 패키지 경로가 들어가지만, **그것은 런타임 등록 완료가 아니다.** 수동으로 같은 경로에 에셋만 만든다고 현재 앱이 INI까지 자동 등록하는 것은 아니다.

에셋 반영은 외부 `UnrealEditor-Cmd` + 앱에 포함된 Python bridge를 사용한다. Row Struct 지정·JSON 입력·저장 코드가 있다. 입력 키는 `RowName`이다. 기존 에셋의 종류/행 구조체가 다르면 차단한다. [Epic Python](https://dev.epicgames.com/documentation/en-us/unreal-engine/scripting-the-unreal-editor-using-python), [Factory](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/DataTableFactory?application_version=5.7)

JSON 채우기 API의 성공은 원본 파일 경로/재임포트 메타데이터까지 완성했다는 의미로 간주하지 않는다. 현재 bridge의 일반 Reimport 메뉴 연계는 별도 확인 대상이다.

### 빌드 경계

| 작업 | C++ 빌드 |
|---|---|
| 값 수정, 같은 구조의 행 추가/삭제 | 이 변경 때문에 재빌드할 필요 없음 |
| 컬럼 추가/삭제/타입 변경 | 필요 |
| 새 행 구조체/Subsystem 멤버/Getter 추가 | 필요 |

신규 C++ 구조의 에셋을 만드는 PC도 해당 코드가 반영된 Editor 모듈을 갖고 있어야 한다. 개발자가 나중에 받으면서 빌드하는 것만으로 생성자 측 조건이 해결되지는 않는다. 빌드 바이너리를 공급받는 운영은 가능하지만 이 도구의 현재 기능은 아니다.

### 다음 개발 방향 — 아직 미구현

**코드·JSON 변환 단계에서 예정 경로 등록을 생성하고, 실제 `.uasset` 생성/존재 확인과 독립시킨다.** 에셋은 개발자가 빌드 후 수동 생성하거나 실험 기능으로 반영한다. 에셋 생성이 수동이어도 Subsystem 코드를 직접 수정하지 않게 하는 것이 목표다.

예정 경로가 `/Game/DataTables/DT_Players.DT_Players`라면 이 경로를 먼저 INI에 기록할 수 있다. 다만 기록됐다는 이유로 `에셋 준비 완료`라고 표시해서는 안 된다. `코드 생성`, `빌드 확인`, `예정 등록`, `에셋 존재`, `엔진 검증` 상태를 분리한다. 구현은 [TD-001](ROADMAP.md)에서 진행한다.

## 7. 소스 구조와 보호 장치

| 파일 | 책임 |
|---|---|
| `main.py` | GUI/샘플/CLI 검증 진입점 |
| `tabledesk/xlsx_reader.py` | 외부 의존성 없는 제한적 OOXML 읽기 |
| `tabledesk/core.py` | 프로젝트/입력 검증, 경로 검사, 생성 계획, manifest, 백업·쓰기 |
| `tabledesk/code_preview.py` | 전체 코드 미리보기 범위 계산 |
| `tabledesk/subsystem_codegen.py` | Subsystem h/cpp 텍스트 생성 |
| `tabledesk/runtime_registration.py` | INI 전용 구역의 소유권 검사·계획·적용 |
| `tabledesk/unreal_runner.py` | 외부 UE 실행/결과/등록 처리 |
| `tabledesk/unreal_bridge.py` | UE 안에서 실행되는 에셋 작업 |
| `tabledesk/gui.py` | 프로젝트 관리/설정/미리보기/진행 UI |

생성 코드와 `.tabledesk-manifest.json`은 함께 관리한다. 수기 파일·외부 변경·해시 불일치·고정 클래스/경로 충돌 시 중단한다. 출력 이름 변경을 이동/삭제로 간주하지 않는다.

현재 백업과 복구 시도는 있지만 전원 차단을 포함한 다중 파일 원자성 보장은 없다. 여러 `.uasset` 저장 중 일부 성공 후 실패할 수 있다. 앱의 작업 잠금은 사용자가 별도로 연 에디터까지 잠그는 장치가 아니다.

## 8. 협업과 검증 수준

도구 저장소에는 앱 소스·문서·샘플·테스트만 둔다. 대상 게임 저장소에는 팀이 공유하는 엑셀 원본, 생성 C++/JSON/manifest, 필요한 INI 변경과 생성 에셋을 관리한다. 앱의 로컬 프로젝트 목록·로그·백업은 커밋하지 않는다.

Git 줄바꿈 변환으로 소유권 해시가 변할 수 있으므로 대상 게임 저장소의 생성 파일은 LF 정책을 검토한다. 기존 파일을 대량 정규화하지 말고 새 clone/OS 변경 테스트를 먼저 수행한다. 팀 공용 설정 이식성은 TD-005에서 다룬다.

Python 테스트/샘플/GUI 검증과 실제 UHT·C++·BP·에셋·패키징 검증은 별개다. 최신 로컬 결과는 [검증 기록](validation/2026-10-10-repository.md), 실제 UE 검증 항목은 [엔진 체크리스트](ENGINE_CHECKLIST.md)를 따른다.
