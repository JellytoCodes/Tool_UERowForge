# 개발·변경 관리

## 저장소의 기준

이 저장소는 UE TableDesk 도구 자체를 관리한다. 실제 게임 프로젝트와 그 결과물은 각 게임 저장소에 둔다. 현재 기능은 v0.2.2이고 다음 작업은 [ROADMAP](docs/ROADMAP.md)에 있다.

`계획 → 구현 → 실행 검증`을 분리한다. 대화에서 합의한 변경은 문서/Issue에 남기고, 구현하지 않은 것을 완료로 표시하지 않는다.

## 개발 환경

Python 3.10+와 Tkinter. 앱 자체는 표준 라이브러리만 사용한다. 선택적인 패키징 도구는 PyInstaller, GUI 화면 캡처만 필요할 때 Pillow를 사용한다. 스크린샷 생성 도구를 앱 필수 의존성으로 만들지 않는다.

```shell
python main.py --demo
python -m unittest discover -s tests -v
python main.py --validate examples/TableTemplate.xlsx
python -m compileall -q main.py tabledesk tests scripts
```

GUI 변경은 디스플레이가 있는 환경에서:

```shell
python scripts/gui_smoke.py
```

Linux headless에서는 `xvfb-run -a python scripts/gui_smoke.py`를 사용한다. 생성 코드 검사는 Unreal UHT/컴파일을 대신하지 않는다.

## 브랜치와 PR

`main`은 검증된 기준선으로 유지한다. 작은 작업도 범위를 분리해 `feat/td-001-planned-registration`, `fix/td-xxx-name`, `docs/topic`처럼 브랜치를 만든다. 이 명칭은 운영 제안이며 원격 보호 규칙이 이미 적용된 것은 아니다.

커밋 예시:

```text
feat: separate planned registration from asset import (TD-001)
fix: preserve unselected table registrations
test: cover schema type mismatch
docs: clarify editor build requirements
```

한 PR에서는 의도한 변경, 실제 동작, 영향 파일, 이관 여부, 실행한 테스트, 미검증 환경을 명시한다. 테이블 Getter를 행 조회 래퍼로 되돌리는 등 기존 결정을 바꾸려면 DECISIONS도 함께 검토한다.

## 테스트와 이관

버그는 가능한 한 재현 테스트를 먼저 추가한다. 기존 fixture를 삭제하거나 해시 검사를 완화해서 통과시키지 않는다. `tests/fixtures/v020`은 실제 구버전 생성물 보존용이므로 바이트와 manifest 관계를 유지한다.

앱 버전은 제품 변화, `GENERATOR_REVISION`은 생성물 호환성이다. 문서/CI 정리만으로 둘을 올리지 않는다. 생성 코드/소유권 형식을 바꾸면 구버전 이관과 이전 버전 재변환 차단을 검토한다.

CI는 Linux/Windows의 Python 단위 테스트와 샘플 검증을 수행하도록 설정돼 있다. GUI smoke는 별도 Linux job이다. 실제 Unreal 엔진과 Windows EXE 검증을 실행했다고 간주하지 않는다. Actions는 원격에 올라가 실제 실행된 뒤 결과를 확인한다.

## 원본과 생성물의 Git 관리

| 도구 저장소에 포함 | 대상 게임 저장소에서 관리 |
|---|---|
| 앱 소스·문서·테스트·샘플 엑셀 | 팀 원본 엑셀, 생성 C++·JSON·manifest, 등록 INI, 실제 DataTable 에셋 |
| CI/Issue/PR 템플릿 | 해당 프로젝트의 모듈/게임 코드/에셋 관리 정책 |

앱 로컬 Registry, 개인 절대 경로, 실행 로그, 백업, 배포 빌드 폴더, 자격증명은 커밋하지 않는다. JSON을 고친 뒤 엑셀을 잊는 방식으로 원본을 분산시키지 않는다.

대상 프로젝트에 생성된 `.tabledesk-manifest.json`은 코드/JSON과 함께 관리해야 한다. `.gitignore`에 모든 점 파일이나 manifest를 무시하는 패턴을 넣지 않는다. 생성물 해시 때문에 LF 정책을 검토하되 기존 프로젝트의 파일 전체를 승인 없이 정규화하지 않는다.

## EXE와 릴리스

개발 중에는 소스로 확인하고, 안정화 후 Windows에서 `build_windows.bat`을 실행한다. onedir 결과의 전체 폴더를 배포한다. 빌드 폴더를 Git 소스에 넣지 않는다. 미리 빌드한 EXE나 GitHub Release는 현재 패키지에 없다.

릴리스 전 단위/GUI/Windows/UE 검증 결과와 지원 범위를 문서화한다. 실제 검증하지 않은 환경은 지원 보장으로 쓰지 않는다.

## 외부 자료

[GitHub Python CI](https://docs.github.com/en/actions/tutorials/build-and-test-code/python), [PyInstaller onedir](https://pyinstaller.org/en/stable/operating-mode.html), [Epic UHT](https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-header-tool-for-unreal-engine).
