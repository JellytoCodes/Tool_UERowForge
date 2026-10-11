# UERowForge

엑셀 데이터를 Unreal Engine의 DataTable에서 사용할 수 있도록 JSON, 행 구조체, DataTableSubsystem 코드를 생성하는 도구.

[Windows 배포본 다운로드](https://github.com/JellytoCodes/Tool_UERowForge/releases/latest)

## 사용법

1. 배포 ZIP을 전체 압축 해제하고 `UERowForge.exe` 실행. `_internal` 폴더도 함께 유지.
2. C++ 프로젝트의 `.uproject` 등록 후 모듈과 접두사 설정.
3. 앱에서 템플릿 저장 후 엑셀 작성 및 불러오기.
4. 변환할 테이블 선택 후 변환.
5. 프로젝트의 Editor 타깃 빌드.
6. 생성된 행 구조체로 DataTable을 만들고 JSON 임포트. Import Key Field는 `RowName`.
7. `DataTableSubsystem`의 Getter로 테이블을 가져와 행 조회.

DataTable은 기본 경로인 `/Game/DataTables/DT_<테이블명>`에 생성. 경로는 Subsystem CPP에 등록됨.

값 변경 후에는 다시 변환하고 해당 DataTable 재임포트. 필드나 에셋 경로를 바꾸면 C++ 재빌드 필요.

배포본은 Python 설치 없이 실행 가능. Unreal Engine과 프로젝트 빌드 환경은 별도로 준비.

## 소스 실행

Python 3.10+ / Tkinter. `Tools/run.bat` 또는 아래 명령으로 실행.

```powershell
python Tools/main.py
```

## 테스트

```powershell
cd Tools
python -m unittest discover -s tests -v
python main.py --validate resources/TableTemplate.xlsx
python -m compileall -q main.py uerowforge tests
python tests/gui_smoke.py
```

[개발 규칙](AGENTS.md) · [MIT](LICENSE.txt)
