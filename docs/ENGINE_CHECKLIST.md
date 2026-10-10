# 실제 Unreal 프로젝트 검증 체크리스트 · v0.2.2

이 문서는 아직 실행하지 않은 **엔진 측 인수 검증 절차**입니다. Python 자동 테스트 통과를 엔진 빌드/런타임 검증으로 간주하지 않습니다. 프로젝트 복사본 또는 복구 가능한 브랜치에서 진행하세요.

v0.2.2는 v0.2.1과 생성 코드가 같습니다. UI 업데이트만을 이유로 아래 빌드/이관 절차를 반복할 필요는 없습니다.
새 테이블/구조체를 생성하거나 v0.2.0 이하에서 이관할 때 해당 절차를 적용하세요.

## 생성 코드와 이관

1. Runtime C++ 모듈과 Core/CoreUObject/Engine 의존성을 확인합니다. `.Build.cs`는 툴이 자동 편집하지 않습니다.
2. 에디터를 종료하고 변환합니다. 행 필드는 `BlueprintReadOnly + Category`, 관리 클래스는 `UDataTableSubsystem`, 테이블은 private TObjectPtr, Getter는 `UFUNCTION(BlueprintPure)` 하나씩인지 확인합니다. 자체 템플릿/Find/TryGet 행 조회 함수는 없어야 합니다.
3. v0.2.0 사용처가 있으면 기존 C++ `FindPlayersRow/TryGetPlayersRow`를 `GetPlayersTable()` + `FindRow<FOBPlayersRow>()`로 고칩니다. 행 타입을 사용하는 호출 파일에 `Data/OBStructTypes.h`를 명시적으로 include합니다. 경로는 프로젝트 설정에 맞춥니다.
4. Editor 타깃 전체 빌드를 수행합니다. UHT 오류, 중복 타입/헤더, API 매크로, include를 점검합니다. Live Coding만으로 검증하지 않습니다. 엔진/외부 플러그인의 동명 클래스는 앱 검사 범위 밖일 수 있습니다.
5. 에디터를 실행해 이전 BP `Try Get ... Row` 노드를 제거하고 새 Getter + 엔진 `Get Data Table Row`로 연결한 뒤 컴파일합니다. v0.1.x에서 업데이트한 경우 기존 행 필드 쓰기 노드도 점검합니다. 앱은 다른 C++ 파일이나 BP를 자동 수정하지 않습니다.

## 에셋 반영과 등록

6. 에셋/등록이 없는 경우 Python Editor Script Plugin / Editor Scripting Utilities를 활성화하고 저장한 뒤 에디터를 종료합니다. 해당 엔진의 UnrealEditor-Cmd를 지정하고 별도 UE 에셋 반영을 실행합니다.
7. DT_Players 등의 RowStruct와 ImportKeyField=RowName, 일반 데이터 필드 Name이 올바른지 확인합니다.
8. 에셋 반영 모두 성공 후 DefaultGame.ini의 UETableDesk.DataTables 구역에 경로가 등록되는지 확인합니다. 기존 에셋·스키마·등록 경로가 동일하면 API 이관만으로 재임포트할 필요는 없습니다. 다른 설정·주석은 보존돼야 합니다.

## Getter와 실제 행 조회

9. BP에서 DataTableSubsystem → Get Players Table로 객체를 얻습니다. 반환 객체가 유효한 경우에만 Get Data Table Row를 호출합니다. Getter는 실행 핀 없는 Pure 노드이며 저장된 객체만 반환해야 합니다.
10. 테이블을 동적으로 연결하면 Out Row를 `OBPlayersRow` 타입의 변수 입력 또는 해당 Break 구조체 입력에 연결해 반환 구조체 타입을 지정합니다. Player_001 조회 성공과 Row Not Found 경로를 모두 확인합니다. 실패 시 기본값 초기화는 예전 래퍼처럼 보장하지 않습니다.
11. C++도 테이블 유효성 → FindRow의 결과 유효성을 순서대로 검사합니다. 잘못된 행 이름/타입 처리와 long-lived 데이터 복사를 검증합니다. 재임포트/종료 후 기존 행 포인터를 재사용하지 않습니다.
12. Getter가 제공하는 객체는 원본입니다. 멤버 포인터 교체는 private이지만 원본 내용 변경은 API 수준에서 제한하지 않습니다. 테스트 중에도 마스터 데이터 변경은 피하고 런타임 상태는 별도 변수로 보관합니다.
13. 같은 GameInstance에서 레벨 이동 전후 테이블/서브시스템 참조를 확인합니다. 새로운 PIE 세션과 서버/클라이언트는 독립 수명이며, 같은 프로세스의 에셋 객체 공유 가능성을 불변성 보장으로 혼동하지 않습니다.
14. 등록 누락·잘못된 경로·다른 RowStruct에서 초기화 로그와 Getter의 nullptr 반환을 확인합니다. Getter 호출 때 재로드·재시도하지 않아야 합니다. 게임 스레드에서 사용합니다.

## 회귀 및 패키징

15. 값만 바꾸면 모든 C++ 파일의 내용·시간이 같아야 합니다. 기존 테이블의 필드만 추가하면 행 헤더는 갱신되지만 서브시스템 h/cpp는 그대로여야 합니다. 구조체 변경 후에는 다시 빌드합니다.
16. 새 테이블 추가 시 기존 멤버·Getter를 유지하면서 새 멤버·Getter·초기화/정리만 추가되는지 확인합니다. 전체 빌드 후 노드를 확인합니다.
17. 쿠킹 규칙은 자동 생성하지 않습니다. 생성 테이블 폴더를 Additional Asset Directories to Cook 또는 Asset Manager 규칙에 포함합니다. INI 문자열만으로 포함된다고 가정하지 않습니다.
18. 패키징한 게임에서 초기 로드·레벨 이동·모든 테이블의 Getter/행 조회를 확인합니다. 에디터 성공만으로 배포 환경 성공을 판정하지 않습니다.

자동 C++ 빌드, 비동기/지연 로딩, 런타임 재등록/재로드, 복제, 대용량 성능, 보안 수준 불변성은 이번 변경 범위가 아닙니다.
