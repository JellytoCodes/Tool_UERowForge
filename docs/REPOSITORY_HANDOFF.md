# 저장소 전환 및 인수인계

정리일: 2026-10-10

## 이번에 준비한 것

v0.2.2 ZIP을 기준으로 로컬 Git `main` 저장소를 만들었다. 첫 커밋은 원본 기준선, 다음 커밋은 문서·작업 목록·CI·Issue/PR 템플릿 정리다. 앱/생성기/테스트/샘플을 기능 변경하지 않았으며 버전은 v0.2.2와 revision 3을 유지한다.

패키지에는 **로컬 `.git` 이력**이 포함돼 있다. 압축을 풀고 `UETableDesk` 폴더를 Git Extensions에서 열면 된다. 프로젝트 자체를 이 도구 폴더 안에 넣을 필요는 없다. 초기 커밋 작성자는 `UE TableDesk contributors`라는 도구용 표기이며 사용자의 GitHub 계정으로 가장하지 않았다.

현재 인수인계 상태:

| 항목 | 상태 |
|---|---|
| 소스/문서/테스트 정리 | 완료 |
| 로컬 Git 초기 커밋 | 완료 |
| GitHub 플러그인 설치 확인 | 확인됨 |
| 이 세션의 GitHub 저장소 조회/쓰기 API | 노출되지 않아 호출 불가 |
| 실제 GitHub 저장소 생성/push | **수행하지 않음** |
| 원격 Issues/PR/Actions 실행 | **수행하지 않음** |

설치 실패라고 판단한 것이 아니다. 설치됨 상태와 실제 작업 도구 노출 상태가 달라, 원격 생성 성공을 주장하지 않는다. 이 파일의 상태는 이번 인수인계 시점 기록이다. 나중에 원격 업로드가 성공하면 실제 URL·커밋·검증 상태로 갱신한다.

## 원격 저장소 설정 제안

이름은 `UETableDesk`, 초기 공개 범위는 **Private**를 제안한다. 이름/계정/공개 여부가 확정됐거나 같은 저장소가 이미 있으면 그 설정을 따른다. 기존 저장소가 있으면 먼저 원격 파일과 이력을 확인하고 덮어쓰지 않는다.

소스가 원격에 올라간 다음 첫 작업으로 TD-001 Issue를 만든다. 앱 버전을 임의로 v0.2.3으로 올리거나 릴리스를 먼저 만들지 않는다.

## GitHub 도구가 정상 노출된 환경에서의 작업 지시

```text
첨부된 UE TableDesk 저장소를 GitHub에서 관리하려고 한다.
README.md, AGENTS.md, docs/PROJECT_SPEC.md, docs/ROADMAP.md를 먼저 읽어라.
사용 가능한 GitHub 계정과 기존 UETableDesk 저장소를 조회해라.
기존 저장소가 없으면 공개 범위를 확인하고 새 저장소를 만들어 이 main을 push해라.
기존 저장소가 있으면 이력을 보존하고 별도 브랜치/PR로 반영해라.
원격 URL과 실제 push된 commit을 확인해라.
문서의 TD-001은 아직 미구현이며 이번에는 앱 기능을 바꾸지 마라.
```

## 로컬에서 직접 최초 업로드하는 대안

GitHub CLI가 설치돼 있고 본인 계정으로 인증된 상태에서, 이 로컬 저장소 루트에서 실행한다. 아래 명령은 **새 비공개 저장소를 만드는 경우만** 사용한다.

```powershell
git status
git log --oneline -2
gh auth status
gh repo create UETableDesk --private --source . --remote origin --push
```

이 명령은 원격 생성/연결/push를 수행한다. 계정을 먼저 확인하고 이름 충돌 시 중단한다. 인증이 없으면 `gh auth login`을 본인 PC에서 진행한다. 토큰을 채팅이나 저장소에 붙여넣지 않는다. [공식 gh repo create](https://cli.github.com/manual/gh_repo_create)

GitHub CLI 대신 웹에서 **초기 README/.gitignore/License를 넣지 않은 빈 저장소**를 만든 뒤, Git Extensions에서 이 폴더를 열고 원격 저장소 주소를 `origin`으로 추가해 `main`을 push해도 된다. 이미 원격에 파일/커밋이 있으면 이 순서로 강제 push하지 않는다.

## 다음 대화/작업에서 넘길 핵심

1. 현재 실행 코드는 v0.2.2. 이번 정리는 기능 리비전이 아니다.
2. 테이블별 Getter만 유지한다. 행 조회 래퍼·자체 템플릿·TMap으로 되돌리지 않는다.
3. 에셋 생성은 빌드 후 별도 단계다. 예정 경로 등록 분리는 다음 작업이다.
4. 현재 INI는 에셋 반영 전체 성공 후에만 작성된다.
5. Python/GUI 결과와 실제 Unreal/Windows/원격 CI 결과는 별개다.
6. 원격 업로드가 확인되기 전까지 저장소/Issue/Release URL을 임의로 만들지 않는다.
