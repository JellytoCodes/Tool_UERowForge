# UERowForge

엑셀에서 Unreal DataTable용 JSON·행 구조체·예정 에셋 경로를 포함한 DataTableSubsystem을 생성하는 도구.

v0.2.2 / 생성기 리비전 5 / Python 3.10+ · Tkinter

Git 배포는 도구·테스트·템플릿·문서만 포함한다. 사용자 프로젝트 `Samples/`와 준비·검증 보조 파일 `Tools/.local/`은 로컬에 보존하고 제외한다.

## 실행

```powershell
python Tools/main.py
```

Windows에서는 `Tools/run.bat`으로 실행.

## 사용

1. `.uproject` 등록 → 모듈·접두사 설정
2. [엑셀 템플릿](Tools/resources/TableTemplate.xlsx) 작성 → 불러오기
3. 테이블 선택 → 검증 → 변환
4. 개발자가 Editor 타깃 빌드 → DataTable 생성·JSON 임포트·저장 → 다음 Play에서 Getter·행 조회 확인

예정 경로는 Subsystem CPP에 직접 생성한다. 값 변경은 JSON과 manifest의 해시만 갱신하며 C++·INI는 유지한다. 스키마·에셋 경로 변경은 C++ 재생성·빌드가 필요하다. 생성 코드·사용자 설정·미선택 테이블의 보호를 유지한다.

일반 변환과 실험 에셋 반영은 INI 등록을 하지 않는다. 구버전 등록 이력이 있으면 소유 해시를 검증한 도구 구역만 한 번 정리·백업하며 외부 변경은 차단한다. UE 에셋 반영은 UE 5.8.3 샘플에서 실행 확인했으며 자동 빌드·쿠킹 설정 변경은 하지 않는다.

## 기존 UE 5.8 샘플

로컬 `Samples/UERowForgeSample.uproject`에 템플릿의 Players·Items를 정식 변환·에셋 반영 기능으로 생성했다. 템플릿은 기존 3행을 보존하고 각 30행으로 확장했으며 마지막 행의 긴 이름으로 가로 넘침도 확인할 수 있다. 기존 `DataTableTest` 맵의 BeginPlay에서 `/Game/UI/WBP_PlayerData`를 표시한다. 상단 드롭다운에서 테이블을 선택하고 휠·오른쪽 막대로 행을, 화면 하단의 고정 막대로 열을 스크롤한다. 전환 시 두 축의 위치를 초기화한다. 작성용 보조 플러그인 없이 동작한다.
JSON·C++는 같은 프로젝트를 연결하고 기본 경로·접두사 `UERFS`로 템플릿을 변환하면 재생성할 수 있다. 표 UMG는 로컬 샘플의 검증 화면이며 도구의 생성 대상에 포함하지 않는다.

| DataTable 경로 | Row Structure (C++) | JSON (Samples 기준) |
|---|---|---|
| `/Game/DataTables/DT_Players` | `FUERFSPlayersRow` | `DataTable/Players.json` |
| `/Game/DataTables/DT_Items` | `FUERFSItemsRow` | `DataTable/Items.json` |

Import Key Field는 `RowName`. 테이블 선택 → Subsystem Getter → 유효성 검사 → 엔진의 행 이름·열 이름·열 값 조회 → 표의 TextBlock 순서다. 열 이름·셀 값은 DataTable에서 읽으며 선택 전환 시 기존 셀을 정리한다. 테이블 없음은 별도 상태, 빈 테이블은 행 수 0으로 표시한다. 특정 행을 타입으로 조회하려면 `Get Data Table Row`의 동적 Out Row를 `Break UERFSPlayersRow` 등 생성된 구조체 입력에 연결한다.

UE 5.8.3 Editor 빌드·BP 컴파일·PIE에서 전체 셀, 30행의 마지막 행·열까지 실제 휠/막대 입력, 전환 후 레이아웃 갱신까지 스크롤 초기화를 확인했다. 임시 복사본에서 이름·MaxHP 100→150·MoveSpeed 600→725.5·Items Weight 1.5→2.25 변경 → 변환 → 재임포트 → 다음 PIE의 표 표시와 원복을 확인했다. C++·INI·미선택 데이터와 사용자 원본은 보존했다. 직접 확인하려면 `DataTableTest`에서 Play하고 테이블을 선택한다. 이후 엑셀 변경 → 변환 → 해당 DataTable 재임포트·저장 → 다음 Play. 패키징·쿠킹은 미검증이다.

UE 5.8 소스상 GameInstance Subsystem 초기화는 일반 Actor BeginPlay보다 먼저 완료된다. 동기 로드는 `Initialize()` 반환 전에 끝난다. 생성자·GameInstance BP Event Init에서 조회하지 않는다. C++ GameInstance의 Init에서는 `Super::Init()` 반환 후, 다른 GameInstance Subsystem의 Initialize에서는 `Collection.InitializeDependency<UDataTableSubsystem>()` 이후 조회한다. 의존성은 같은 컬렉션에서만 유효하며 순환 의존은 피한다. BeginPlay에서 만든 UMG의 Construct에서 조회할 수 있지만 테이블·행 유효성 검사는 필요하다.

## 검증

```powershell
cd Tools
python -m unittest discover -s tests -v
python main.py --validate resources/TableTemplate.xlsx
python -m compileall -q main.py uerowforge tests
python tests/gui_smoke.py
```

[개발 규칙](AGENTS.md) · [MIT](LICENSE.txt)
