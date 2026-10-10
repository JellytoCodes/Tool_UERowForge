# 저장소 정리 후 검증 기록

검증일: 2026-10-10. 환경: Linux, Python 3.13.5, Tk 8.6, Xvfb.

**이번 작업은 v0.2.2 소스를 Git 저장소 형태로 정리한 문서/관리 변경이다. 앱/생성기 버전은 올리지 않았다.** 원본 ZIP의 SHA-256과 파일 비교 요약은 [저장소 검사 결과](logs/repository-checks.json)에 있다.

## 실제 실행 결과

| 검증 | 결과 | 증거 |
|---|---|---|
| `python -m unittest discover -s tests -v` | **144개 통과**, 실패/skip 없음 | [전체 출력](logs/unittest.txt) |
| `python main.py --validate examples/TableTemplate.xlsx` | Players/Items 각 3행, 오류 0건 | [JSON 결과](logs/sample-validation.json) |
| `python -m compileall -q main.py tabledesk tests scripts` | 종료 코드 0 | 현재 컨테이너에서 직접 실행 |
| `xvfb-run -a python scripts/gui_smoke.py` | 통과 | [GUI 출력](logs/gui-smoke.txt) |
| 원본 v0.2.2와 보호 대상 비교 | **41개 파일 바이트 동일** | [검사 결과](logs/repository-checks.json) |
| GitHub 설정 YAML 4개 | 구문 파싱 및 기본 구조 검사 통과 | 원격 실행/공식 actionlint 결과는 아님 |
| 문서 상대 링크 | 존재 여부 검사 통과 | 검증 페이지는 작성 후 다시 검사 |
| 토큰/개인키 패턴 검사 | 대상 텍스트에서 일치 0건 | 제한적 패턴 검사이며 전체 보안 감사를 뜻하지 않음 |

보호 대상은 기존 `.py`, `.bat`, `.xlsx`, `.h`, `.cpp`, `.json`, `.png` 및 LICENSE다. 원본 앱·생성 코드·샘플·과거 fixture는 그대로 유지했다. 기존 README_KO/VALIDATION/CHANGELOG에는 문서 안내만 추가했다.

## GUI에서 확인한 것

전체 C++ 파일 미리보기, 테이블 선택과 공통 코드 범위 분리, 최종 선택 변환과 미리보기 일치, 전체 코드 복사, 미리보기의 무쓰기, 기존 테이블 보존, 외부 변경 오류 표시/복구, 설정/경로, 실제 파일 생성, 반복 변환 no-op를 다시 확인했다.

기존 docs의 PNG는 원본 배포본에 포함된 화면이며 이번 작업에서 새로 그린 모형이나 새 캡처로 교체하지 않았다.

## 미실행 / 미검증

- 실제 Unreal UHT/C++ 컴파일·링크, BP 노드, 런타임 로드/수명, `.uasset` 생성·갱신, 패키징.
- Windows GUI/배치 실행/PyInstaller EXE와 Python이 없는 PC 실행.
- Python 3.10 실행. CI matrix에는 설정했지만 이번 로컬 테스트는 3.13.5다.
- GitHub 저장소 생성/push, 원격 Issues/PR, 원격 Actions 실행, Release 게시.
- TD-001 예정 경로 사전 등록 기능. 문서화만 했으며 코드에 아직 반영하지 않았다.

원격 CI가 녹색이 된 것처럼 badge를 넣지 않았고, 로컬 테스트를 원격/Windows/Unreal 성공으로 표현하지 않았다.
