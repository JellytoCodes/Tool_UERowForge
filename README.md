# UERowForge

엑셀에서 Unreal DataTable용 JSON과 C++ 코드를 생성하는 Python/Tkinter 도구입니다.
여러 C++ 프로젝트를 등록해 사용할 수 있습니다.

v0.2.2 · 생성기 리비전 3 · [MIT](LICENSE.txt)

## 실행

Python 3.10 이상과 Tkinter가 필요합니다. 앱 실행에는 외부 패키지가 필요하지 않습니다.

```powershell
python Tools/main.py
python Tools/main.py --demo
```

Windows에서는 `Tools/run.bat`으로 실행할 수 있습니다. `--demo`는 파일 변환용 임시 프로젝트를 사용합니다.

## 사용법

1. **프로젝트 추가**에서 `.uproject`가 있는 폴더를 선택하고 모듈·접두사·출력 경로를 설정합니다.
2. [엑셀 템플릿](Tools/resources/TableTemplate.xlsx)을 복사해 데이터를 입력한 뒤 불러옵니다.
3. 검증된 테이블을 선택하고 **선택 항목 변환**을 누릅니다. 최종 확인 창에서 변경 내용을 확인하고 저장합니다.

엑셀을 수정한 뒤에는 **다시 읽기 / 검증**을 누릅니다. Blueprint 전용 프로젝트는 먼저 C++ 모듈을 추가해야 합니다.

## 엑셀 형식

시트 하나가 테이블 하나입니다. `_`로 시작하는 시트는 건너뜁니다.

| 행 | A | B | C | D |
|---|---|---|---|---|
| 1 | TableName | Players | | |
| 2 | RowName | RawName | Name | ID |
| 3 | RowKey | String | Name | Int |
| 4 이후 | Player_001 | 기본 플레이어 | PlayerBasic | 1 |

| 타입 | C++ | 빈 셀 |
|---|---|---|
| String / FString | FString | 빈 문자열 |
| Name / FName | FName | NAME_None |
| Int / int32 | int32 | 오류 |
| Float | float | 오류 |
| Bool | bool | 오류 |

- 첫 컬럼은 `RowName / RowKey`입니다. 행 키는 C++ 멤버로 생성하지 않습니다.
- 테이블·필드명은 영문으로 시작하는 영문·숫자·밑줄 조합입니다.
- 행 키는 영문·숫자·밑줄·하이픈 1~128자입니다. `None`과 대소문자만 다른 중복은 허용하지 않습니다.
- Bool은 `TRUE/FALSE` 또는 `1/0`으로 입력합니다. 타입명은 대소문자를 구분하지 않습니다.
- 하위 경로가 필요하면 D1에 `SubPath`, E1에 상대 경로를 입력합니다. 기본값은 빈 칸이며 앱 설정이 우선합니다.

`.xlsx`만 지원합니다. 수식·날짜·병합 셀·배열·Enum·FText·중첩 구조체·에셋 참조는 지원하지 않습니다.
파일은 32 MiB, 테이블은 50,000행·128열까지 읽습니다. 빈 테이블로 기존 데이터를 지우는 작업은 지원하지 않습니다.

## 생성 결과

기본 출력 경로입니다. 접두사는 행 헤더와 구조체 이름에만 적용합니다.

```text
Source/<Module>/Public/Data/<Prefix>StructTypes.h
Source/<Module>/Public/Data/DataTableSubsystem.h
Source/<Module>/Public/Data/.tabledesk-manifest.json
Source/<Module>/Private/Data/DataTableSubsystem.cpp
DataTable/<Table>.json
```

행은 `FTableRowBase`를 상속하며 필드는 `BlueprintReadOnly`입니다.
`UDataTableSubsystem`은 GameInstance 초기화 시 테이블을 로드하고 `Get<Table>Table()`로 포인터를 반환합니다.
호출 측에서 null과 행 존재 여부를 확인해야 합니다. Getter로 받은 원본 테이블은 수정하지 않습니다.

데이터·JSON은 테이블별로, C++는 파일 전체를 미리 봅니다. 공통 코드 미리보기에는 정상 입력 전체와 기존 테이블이 포함되며, 선택 항목의 실제 저장 결과는 최종 확인 창에서 확인합니다.
미선택 테이블은 보존합니다. 값이나 행만 바뀌면 C++ 재빌드가 필요하지 않습니다.

## UE 에셋 반영

에셋 반영은 실험 기능입니다. 일반 변환은 JSON·C++·manifest를 저장하며 INI는 쓰지 않습니다.

1. 프로젝트의 **Python Editor Script Plugin**과 **Editor Scripting Utilities**를 활성화합니다.
2. 프로젝트를 연 에디터를 모두 종료하고 생성 C++를 포함해 Editor 타깃을 빌드합니다.
3. 프로젝트 설정에 `UnrealEditor-Cmd.exe` 경로를 지정한 뒤 **UE 에셋 반영**을 실행합니다.

예정 경로는 `/Game/DataTables/DT_<Table>`입니다. JSON은 기존 행 데이터를 전체 교체합니다.
선택 에셋이 모두 저장되면 `Config/DefaultGame.ini`의 `UETableDesk.DataTables` 구역에 등록합니다.
같은 경로에 에셋을 수동 생성하는 것만으로는 INI에 등록되지 않습니다.

자동 빌드·플러그인 활성화·쿠킹 설정은 지원하지 않습니다. 에셋 저장 중 실패하면 일부 에셋이 반영된 상태로 남을 수 있습니다.
실제 UE 빌드·BP·런타임·에셋 반영·패키징은 아직 검증하지 않았습니다.

## 파일 관리

생성 파일과 `.tabledesk-manifest.json`을 함께 관리합니다. 수기 파일이나 외부 수정이 발견되면 덮어쓰기를 중단합니다.
백업은 대상 프로젝트의 `Saved/TableDesk`에 저장합니다. 경로 변경 시 기존 파일을 자동 이동·삭제하지 않습니다.
`TABLEDESK` 마커와 기존 INI·manifest·Saved 경로는 구버전 생성물과의 호환을 위해 유지합니다.

로컬 프로젝트 목록은 `%LOCALAPPDATA%/UERowForge/projects.json`에 저장합니다.
설정 위치는 `UEROWFORGE_HOME`으로 바꿀 수 있으며 구버전 `TABLEDESK_HOME`도 지원합니다.

`Samples/`에는 UE 5.8 샘플 프로젝트가 있습니다. 소스·Config·Content는 Git으로 관리하고 빌드·캐시·Saved는 제외합니다.

## 개발

앱·템플릿·테스트는 `Tools/`에 있습니다. 개발 규칙은 [AGENTS.md](AGENTS.md)를 참고합니다.

```powershell
cd Tools
python -m unittest discover -s tests -v
python main.py --validate resources/TableTemplate.xlsx
python -m compileall -q main.py uerowforge tests
python tests/gui_smoke.py
```

EXE는 `py -3 -m pip install pyinstaller` 후 `Tools/build_windows.bat`으로 빌드합니다.
`Tools/dist/UERowForge/` 폴더 전체를 배포합니다. Windows EXE 빌드·실행은 아직 검증하지 않았습니다.

## 다음 작업

우선 **TD-001: 에셋 생성 전 예정 경로 등록**을 구현합니다. `.uasset` 없이 코드·JSON·INI를 준비하고, 빌드 후 수동 생성한 에셋도 코드 수정 없이 로드하는 것이 목표입니다.

이후 실제 UE 연동, EXE·패키징, 팀 설정 공유와 실패 복구를 검증합니다.
파일 삭제·이동과 지원 타입 확장은 보류합니다.
