# UE TableDesk 작업 지침

## 먼저 읽을 것

`README.md` → `docs/PROJECT_SPEC.md` → `docs/DECISIONS.md` → `docs/ROADMAP.md`를 읽고, 작업 대상의 현재 구현을 확인한다. 채팅의 오래된 설계를 그대로 복원하지 않는다. 문서와 코드가 충돌하면 현재 동작과 변경 의도를 분리해 보고한다.

## 유지할 설계

- 공용 Python/Tkinter 데스크톱 앱. 기본 실행은 표준 라이브러리만 사용한다. 의존성·프레임워크를 추가하려면 먼저 필요성을 제시한다.
- 프로젝트는 `.uproject` 단위로 등록하고 작업 화면의 루트는 잠근다. 사용자가 수정하는 출력 경로는 허용 기준 폴더 내부의 상대 경로다.
- 기본 행/Subsystem 헤더 경로는 `Source/<Module>/Public/Data`, CPP는 `Source/<Module>/Private/Data`다. JSON은 `<Project>/DataTable`이다.
- 테이블별 추가 경로는 `""`이다. 문자열 `Null`/`None`을 기본 경로로 만들지 않는다. 기존 사용자 설정을 강제로 덮어쓰지 않는다.
- 행은 `USTRUCT(BlueprintType)` 및 `FTableRowBase` 상속을 유지한다. 필드는 **`UPROPERTY(BlueprintReadOnly, Category = "<Table>")`**로 고정한다.
- 승인 없이 `EditAnywhere`, `EditDefaultsOnly`, `BlueprintReadWrite`, 추가 `meta` UI를 다시 넣지 않는다.
- 관리 클래스는 **`UDataTableSubsystem : public UGameInstanceSubsystem`** 한 개다. 파일명은 `DataTableSubsystem.h/.cpp`; 프로젝트 접두사를 붙이지 않는다.
- 테이블마다 private `UPROPERTY(Transient) TObjectPtr<UDataTable>`와 public `UFUNCTION(BlueprintPure, Category="DataTable") UDataTable* Get<Table>Table() const` 하나만 만든다.
- **TMap 테이블 저장소, `Find<Table>Row`, `TryGet<Table>Row`, 자체 로드 템플릿을 다시 도입하지 않는다.** 엔진 API 자체의 `LoadObject<UDataTable>` 템플릿 사용은 이 금지에 해당하지 않는다.
- 로더는 `.cpp` 내부의 `LoadRegisteredTable(const TCHAR*, const UScriptStruct*)` 일반 함수로 유지한다. 등록 누락·로드 실패·행 타입 검사는 없애지 않는다.
- 행 헤더는 Subsystem `.cpp`에서 include한다. Subsystem `.h`가 행 헤더를 다시 전이 include하도록 하지 않는다.
- Getter는 공유 원본을 반환한다. `BlueprintReadOnly`나 Getter가 원본 전체의 불변성을 보장한다고 설명하지 않는다.

## 현재 구현과 목표를 혼동하지 말 것

현재 앱은 **v0.2.2**, `GENERATOR_REVISION=3`이다. 소스 배포본이며 실제 Unreal/Windows EXE 검증은 끝나지 않았다.

현재 `runtime_registration.py`는 에셋 반영 전체 성공 후에만 `DefaultGame.ini`를 쓴다. `core.py`의 일반 변환은 이 INI를 쓰지 않는다. **에셋 생성 전 예정 경로 등록(TD-001)은 미구현**이다. 이 작업을 하지 않은 PR에서 이미 지원한다고 문서를 바꾸지 않는다.

새 C++ 구조체와 Getter를 만들어 놓고 빌드 전 `.uasset`을 정상 생성할 수 있다고 가정하지 않는다. `.uasset` 바이너리를 외부 Python에서 직접 조립하거나 가짜 구조체로 우회하지 않는다. 자동 C++ 빌드/프로젝트 플러그인 활성화/쿠킹 변경은 별도 승인 작업이다.

## UI 불변 조건

테이블 데이터·JSON은 포커스 테이블별 미리보기다. C++는 행 헤더, Subsystem 헤더, Subsystem CPP **전체 파일**이다. 테이블 선택을 바꿔도 공통 코드 범위는 바뀌지 않는다.

공통 미리보기는 정상 입력 전체 + 기존 관리 테이블이고, 실제 선택 변환은 선택 입력 + 기존 관리 테이블이다. 최종 확인 화면은 실제 저장 결과를 보여야 한다. 미리보기/복사는 디스크 쓰기를 하지 않는다.

## 파일 보호

수기 파일·소유권 없는 생성물·외부 변경은 자동 덮어쓰지 않는다. 해시 검사, 경로 정규화, 프로젝트 및 기준 폴더 내부 제한, 백업, 실패 복구 시도, 미선택 테이블 보존을 유지한다.

`.tabledesk-manifest.json`은 관리 상태의 일부다. 무시·삭제·빈 파일 재생성으로 충돌을 우회하지 않는다. 생성 형식 변경 시 revision과 이관 테스트를 함께 검토한다. 앱 버전과 generator revision은 별개다.

필드/행 키/테이블/경로 변경으로 기존 C++·BP 참조를 자동 이관했다고 주장하지 않는다. 실사용 프로젝트로 첫 테스트를 하지 말고 임시 프로젝트/fixture를 사용한다.

## 작업 절차

작업 전 `git status`로 사용자 변경을 확인한다. 이번 Issue 범위만 수정하고 승인되지 않은 구조 재설계, 전체 포맷팅, unrelated cleanup은 하지 않는다.

```text
변경 의도 확인 → 해당 코드/테스트 읽기 → 최소 수정 → 회귀 테스트
→ 문서/CHANGELOG 반영 → diff와 미검증 범위 보고
```

필수 명령:

```shell
python -m unittest discover -s tests -v
python main.py --validate examples/TableTemplate.xlsx
python -m compileall -q main.py tabledesk tests scripts
```

GUI 변경이면 디스플레이가 있는 환경에서 `python scripts/gui_smoke.py`도 실행한다. Linux headless에서는 `xvfb-run -a python scripts/gui_smoke.py`를 사용한다. Unreal 테스트는 별도다. 실패·skip·미실행을 숨기지 않는다.

## 보고·외부 작업

한국어 문서/설명은 간결하고 구체적으로 쓴다. `계획`, `구현`, `실행 검증`을 구분한다. 문서/Issue 템플릿 생성만으로 GitHub Issue가 등록되었다고 보고하지 않는다.

저장소 공개 전환, 강제 push, 기존 원격 이력 교체, 릴리스 게시, 사용자 프로젝트 대량 수정은 임의로 진행하지 않는다. 토큰/비밀번호/실사용 원본 데이터를 커밋하지 않는다. 도구 저장소와 대상 Unreal 프로젝트 저장소를 혼동하지 않는다.
