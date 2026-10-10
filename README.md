# UE TableDesk

**엑셀에서 Unreal DataTable용 JSON·행 구조체·관리 서브시스템을 생성하는 경량 데스크톱 도구.**

Python + Tkinter 기반의 공용 프로그램 하나에 여러 Unreal 프로젝트를 등록합니다. 기획자는 엑셀을 원본으로 관리하고, 도구가 반복적인 데이터 변환과 코드를 생성합니다. 프로젝트마다 도구를 복사하지 않습니다.

**현재 앱: v0.2.2 · 생성기 리비전: 3 · 상태: 프로토타입**

> 이 저장소 정리에서는 앱 기능을 변경하지 않았습니다. `.uasset` 생성은 이미 코드가 있는 **실험 기능**이며, 실제 Unreal 실행 검증은 끝나지 않았습니다. **에셋 생성 전 예정 경로 등록은 아직 미구현**입니다.

## 시작하기

Python 3.10 이상과 Tkinter가 필요합니다. 앱 실행에 필요한 별도 pip 패키지는 없습니다.

```powershell
python main.py
```

Windows에서는 `run.bat`으로 실행해도 됩니다. 실제 프로젝트를 건드리지 않고 확인하려면:

```powershell
python main.py --demo
```

데모는 파일 변환용 모형 프로젝트입니다. 실제 Unreal 프로젝트로 빌드하거나 에셋 반영에 사용하지 않습니다.

프로젝트 폴더 등록 → 대상 모듈·접두사 설정 → 엑셀 불러오기 → 검증/미리보기 → 선택 항목 변환 순서입니다. 자세한 입력 규격과 이전 버전 이관 방법은 [사용 설명서](README_KO.md)를 참고하세요.

## 현재 구현과 남은 작업

| 영역 | v0.2.2 현재 상태 |
|---|---|
| 여러 프로젝트 등록·전환·등록 해제 | 구현. 등록 해제는 실제 프로젝트 파일을 삭제하지 않음 |
| `.xlsx` 읽기·검증·JSON 출력 | 구현. 시트 하나를 테이블 하나로 처리 |
| 행 구조체·`UDataTableSubsystem` 생성 | 구현. 테이블별 private 포인터 + public Getter |
| 데이터/JSON 개별 미리보기, C++ 파일 전체 미리보기 | 구현 |
| 파일 소유권·해시·백업·부분 선택 변환 | 구현. 일부 파일의 실패 복구는 원자적 트랜잭션 보장이 아님 |
| `.uasset` 생성·갱신·저장 | 실험 코드 존재. 먼저 해당 Editor C++ 빌드가 필요 |
| 런타임 INI 등록 | **UE 에셋 반영 전체 성공 후에만** 자동 등록 |
| 코드·JSON 변환만으로 예정 에셋 경로 등록 | **미구현. 다음 작업 TD-001** |
| 자동 C++ 빌드 / 자동 쿠킹 설정 | 미구현 |
| Windows EXE | `build_windows.bat` 제공. 빌드·실행 검증 및 EXE 배포는 별도 |

## 생성 규칙

```text
OperationBreakpoint/
├─ Source/OperationBreakpoint/
│  ├─ Public/Data/
│  │  ├─ OBStructTypes.h
│  │  ├─ DataTableSubsystem.h
│  │  └─ .tabledesk-manifest.json
│  └─ Private/Data/
│     └─ DataTableSubsystem.cpp
├─ DataTable/
│  ├─ Players.json
│  └─ Items.json
└─ Content/DataTables/
   ├─ DT_Players.uasset    # 별도 에셋 반영 단계
   └─ DT_Items.uasset
```

추가 하위 경로는 **빈 값이 기본**입니다. 접두사 `OB`는 예시이며 행 헤더·행 구조체에만 적용합니다. 관리 클래스명은 `UDataTableSubsystem`으로 고정합니다.

```cpp
// 행 필드: BP 읽기 허용, 편집/쓰기 지정자는 생성하지 않음
UPROPERTY(BlueprintReadOnly, Category = "Players")
int32 ID = 0;

// UDataTableSubsystem 내부
public:
    UFUNCTION(BlueprintPure, Category = "DataTable")
    UDataTable* GetPlayersTable() const { return PlayersTable.Get(); }

private:
    UPROPERTY(Transient)
    TObjectPtr<UDataTable> PlayersTable = nullptr;
```

Getter는 공유 원본 객체를 반환합니다. 멤버 재대입만 private으로 제한하며 **원본 내용의 불변성은 보장하지 않습니다.** 행 조회와 실패 처리는 호출 측에서 담당합니다.

## C++와 에셋의 작업 경계

**값 수정·행 추가/삭제**는 구조가 같다면 데이터 작업입니다. **테이블·컬럼·타입 변경으로 C++가 바뀌면** Editor 타깃 빌드가 먼저 필요합니다. 에셋은 이름만 기록하는 파일이 아니라 실제 로드된 Row Struct 정보로 생성합니다. [UHT](https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-header-tool-for-unreal-engine), [DataTableFactory](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/DataTableFactory?application_version=5.7)

장기 방향은 **기획자용 코드·JSON 변환**과 **개발자용 빌드 후 에셋 반영**을 분리하는 것입니다. 수동으로 만든 에셋도 예정 경로만 맞으면 Subsystem에서 읽도록 만들되, 이를 위한 사전 등록 기능은 아직 남은 작업입니다.

## 개발·검증

```powershell
python -m unittest discover -s tests -v
python main.py --validate examples/TableTemplate.xlsx
python -m compileall -q main.py tabledesk tests scripts
```

[검증 기록](docs/validation/2026-10-10-repository.md)은 실제 실행 결과와 미검증 항목을 구분합니다. Python 코드 생성 테스트 통과를 Unreal 컴파일 성공으로 간주하지 않습니다. GitHub Actions 설정은 [CI](.github/workflows/ci.yml)에 있으며 원격 실행 결과는 별도입니다.

## 문서 안내

| 문서 | 용도 |
|---|---|
| [PROJECT_SPEC](docs/PROJECT_SPEC.md) | 전체 요구사항·경로·생성 규칙·현재와 목표의 구분 |
| [DECISIONS](docs/DECISIONS.md) | 왜 이 설계를 선택했는지, 폐기한 대안 |
| [ROADMAP](docs/ROADMAP.md) | 우선순위와 완료 조건이 있는 다음 작업 |
| [AGENTS](AGENTS.md) | Codex 등 코드 작업자가 지켜야 할 규칙 |
| [CONTRIBUTING](CONTRIBUTING.md) | 브랜치·커밋·테스트·리뷰 절차 |
| [REPOSITORY_HANDOFF](docs/REPOSITORY_HANDOFF.md) | 저장소 도입 상태와 최초 GitHub 연결 절차 |
| [README_KO](README_KO.md) | v0.2.2 상세 사용법·엑셀 규격·이관 |
| [ENGINE_CHECKLIST](docs/ENGINE_CHECKLIST.md) | 실제 Unreal 인수 테스트 |
| [CHANGELOG](CHANGELOG.md) | 버전별 변경 이력 |

대화에서 나온 새 결정은 문서와 Issue에 반영합니다. 구현 완료는 코드·검증 결과가 있는 경우에만 표시합니다.

라이선스는 기존 배포본의 [MIT License](LICENSE.txt)를 유지합니다.
