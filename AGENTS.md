# UERowForge 개발 규칙

`README.md`와 작업할 코드·테스트를 읽는다. 현재 앱은 v0.2.2, 생성기 리비전은 3이다.
**문서는 README.md와 이 파일 두 개만 관리한다.** 사용법/현황/다음 작업은 README, 개발 제약은 여기 둔다.
별도 명세·로드맵·결정 기록·CHANGELOG·검증 보고서·절차/템플릿 문서를 임의로 만들지 않는다. 이력은 Git, 세부 작업은 실제 Issue/PR에 남긴다.

## 고정 설계

제품·저장소·배포 이름은 **UERowForge**, Python 패키지는 `Tool/uerowforge`다.
`UDataTableSubsystem`과 기존 C++ 생성 규칙은 제품명을 따라 바꾸지 않는다.
기존 생성물/INI/잠금의 `TABLEDESK`, `UETableDesk.DataTables`, `.tabledesk-manifest.json`, `Saved/TableDesk`는 호환 식별자다.
현재 명칭 변경은 generator revision 3과 출력 바이트를 유지한다. 이를 바꾸려면 별도 이관 작업으로 다룬다.
기본 설정은 `UERowForge`에 저장하고 최초 실행 시 유효한 구버전 설정만 원본을 보존한 채 복사한다.
`UEROWFORGE_HOME` 우선, `TABLEDESK_HOME` 호환 지원. 사용자가 지정한 별도 설정 위치는 자동 이관하지 않는다.

- Python + Tkinter 공용 앱. 기본 실행은 표준 라이브러리만 사용한다. 새 의존성·프레임워크는 승인 없이 추가하지 않는다.
- 프로젝트 루트는 연결 후 고정한다. 출력은 허용 기준 폴더 안의 상대 경로만 받는다.
- 기본 헤더는 `Source/<Module>/Public/Data`, CPP는 `Source/<Module>/Private/Data`, JSON은 `<Project>/DataTable`, 에셋은 `/Game/DataTables`다.
- 추가 하위 경로는 `""`가 기본이다. 사용자의 기존 경로 설정은 유지한다. 테이블 이름으로 폴더를 자동 분리하지 않는다.
- 접두사는 `<Prefix>StructTypes.h`와 `F<Prefix><Table>Row`에만 적용한다. API 매크로는 실제 모듈명 기준이다. 테이블명을 단수/복수로 임의 변환하지 않는다.
- 행은 `USTRUCT(BlueprintType)`와 `FTableRowBase` 상속. 필드는 **`UPROPERTY(BlueprintReadOnly, Category = "<Table>")`**만 생성한다.
- EditAnywhere/EditDefaultsOnly/BlueprintReadWrite 및 추가 meta UI를 되살리지 않는다. `.generated.h`는 마지막 include이며 직접 생성하지 않는다.
- 관리 클래스는 **`UDataTableSubsystem : public UGameInstanceSubsystem`**, 파일명은 `DataTableSubsystem.h/.cpp`로 고정한다.
- 테이블마다 private `UPROPERTY(Transient) TObjectPtr<UDataTable>`와 public `UFUNCTION(BlueprintPure, Category="DataTable") UDataTable* Get<Table>Table() const` 하나만 생성한다.
- **TMap 저장, Find/TryGet 행 조회 래퍼, Setter, 자체 로드 템플릿을 추가하지 않는다.** 엔진 API의 `LoadObject<UDataTable>` 사용은 금지 대상이 아니다.
- 공통 로더는 `.cpp` 내부의 `LoadRegisteredTable(const TCHAR*, const UScriptStruct*)` 일반 함수다. 등록 누락·로드 실패·행 타입 검사를 유지한다.
- 초기화 시 테이블별 동기 로드/보관, 종료 시 참조 정리. Getter는 포인터 반환만 수행한다. Tick/레벨별 재로드/static 싱글턴을 추가하지 않는다.
- 행 헤더는 Subsystem `.cpp`에서만 include한다. Getter의 공유 원본 반환을 불변성 보장으로 설명하지 않는다.

## UI·파일 보호

데이터/JSON은 포커스 테이블별, C++는 행 헤더/Subsystem 헤더/CPP **전체 파일** 미리보기다.
공통 미리보기는 정상 입력 전체 + 기존 관리 테이블, 실제 변환은 선택 입력 + 기존 관리 테이블이다.
테이블 선택 변경이 공통 코드 범위를 바꾸지 않는다. 최종 확인은 실제 저장 결과와 같아야 한다. 미리보기/복사는 읽기 전용이다.

경로 정규화·허용 폴더 제한·원본/생성물 해시·백업·복구 시도·미선택 테이블 보존을 유지한다.
수기 코드·외부 수정·동명 클래스/파일 충돌은 중단한다. manifest 삭제/해시 조작으로 우회하지 않는다.
생성 포맷 변경은 revision과 이관 테스트를 검토한다. 앱 버전과 generator revision은 별개다.
이름·경로 변경을 자동 삭제/이동으로 간주하지 않는다. 사용자 C++·BP 참조를 이관했다고 주장하지 않는다.

## 현재 동작과 다음 변경

**현재 일반 변환은 INI를 쓰지 않는다.** `Tool/uerowforge/runtime_registration.py`의 등록은 `Tool/uerowforge/unreal_runner.py`에서 에셋 전체 저장 성공 후 수행한다.
**TD-001(사전 예정 경로 등록)은 미구현**이다. 이를 구현하지 않고 문서만 완료로 바꾸지 않는다.

TD-001은 코드/JSON 변환 계획에 INI 예정 경로를 포함하되 실제 에셋 준비 상태와 분리하는 작업이다.
`.uasset` 없는 상태의 등록, 기존 구역·미선택 테이블·인코딩 보존, 외부 변경 차단, no-op, 구버전 이관/실패 복구를 테스트한다.
마지막 완료 확인은 빌드 후 같은 경로에 수동 생성한 정상 에셋이 Subsystem 코드 수정 없이 로드되는 실제 UE 테스트다.

신규 C++ 구조체를 빌드하기 전 에셋 생성이 가능하다고 가정하지 않는다. 가짜 구조체나 외부 Python의 uasset 바이너리 직접 작성으로 우회하지 않는다.
자동 C++ 빌드·플러그인 활성화·쿠킹 설정 변경은 별도 작업이다. 부분 저장을 전체 롤백으로, Python 테스트를 Unreal 빌드 성공으로 설명하지 않는다.

## 소스 위치·작업 절차

| 위치 | 역할 |
|---|---|
| `Tool/main.py`, `Tool/uerowforge/gui.py` | 진입점·UI |
| `Tool/uerowforge/xlsx_reader.py`, `Tool/uerowforge/core.py` | 엑셀 읽기·검증·경로·코드/JSON 계획·manifest·파일 보호 |
| `Tool/uerowforge/subsystem_codegen.py`, `Tool/uerowforge/code_preview.py` | Subsystem 생성·전체 코드 미리보기 |
| `Tool/uerowforge/runtime_registration.py`, `Tool/uerowforge/unreal_runner.py`, `Tool/uerowforge/unreal_bridge.py` | INI 등록·외부 UE 실행·엔진 내부 에셋 작업 |
| `Tool/tests/`, `Tool/tests/gui_smoke.py` | 회귀 테스트·GUI 테스트 |

`Tool/tests/fixtures/v020`은 원본 v0.2.0 생성물을 보존한 이관 입력이다. 현재 생성 예시로 수정하거나 게임에 복사하지 않는다.
템플릿 엑셀의 유일한 원본은 **`Tool/resources/TableTemplate.xlsx`**다. 앱·데모·테스트·EXE가 모두 이를 사용한다.
**`Samples`는 사용자가 UE 5.8 프로젝트를 직접 만들어 넣는 곳이다.** 승인 없이 `.uproject`나 샘플 C++/에셋을 생성하지 않는다.
테스트와 앱이 특정 샘플 프로젝트명/모듈명에 의존하면 안 된다. `--demo`는 로컬 임시 모형만 사용하는 별도 기능이다.
사용자 샘플의 바이너리/캐시를 Git이나 EXE 번들에 넣지 않는다. 샘플을 임의 수정/이동/삭제하지 않는다.
루트는 `Tool`, `Samples`, 기존 문서/라이선스/Git 설정으로 유지한다. 도구용 폴더는 `Tool` 아래에 둔다.
`scripts`, 별도 화면 캡처/샘플 생성 코드/문서 폴더를 루트에 다시 늘리지 않는다.
fixture 출처와 구버전 문서는 기존 Git 이력에 남아 있다.

작업 전 `git status`로 사용자 변경을 확인한다. 요청 범위만 최소 수정하고 기능 변경 시 테스트와 README 현황을 함께 갱신한다.
테스트 명령은 README의 검증 절에 있다. GUI 변경은 GUI smoke를 추가 확인한다.
문서 경로를 바꾸면 GUI의 `사용 설명서` 버튼과 `Tool/build_windows.bat`의 번들 경로도 확인한다.

보고는 변경 내용·실제 테스트 결과·미검증 범위만 간단히 적는다. 새 문서 수를 성과로 취급하지 않는다.
원격 공개·강제 push·기존 이력 교체·릴리스 게시·실사용 프로젝트 대량 변경은 임의로 진행하지 않는다.
토큰/개인 경로/실사용 데이터를 커밋하지 않는다. 도구 저장소와 대상 게임 저장소를 구분한다.
