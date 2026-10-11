# UERowForge

엑셀에서 Unreal DataTable용 JSON·행 구조체·DataTableSubsystem을 생성하는 도구.

v0.2.2 / Python 3.10+ · Tkinter

## 실행

```powershell
python Tools/main.py
```

Windows에서는 `Tools/run.bat`으로 실행.

## 사용

1. `.uproject` 등록 → 모듈·접두사 설정
2. [엑셀 템플릿](Tools/resources/TableTemplate.xlsx) 작성 → 불러오기
3. 테이블 선택 → 검증 → 변환

UE 에셋 반영은 미검증 실험 기능. Editor 타깃 빌드가 필요하며, 에셋 전체 저장 성공 후 INI에 등록.

다음 작업: 에셋 생성 전 예정 경로 등록(TD-001), 실제 UE 연동 검증.

## 검증

```powershell
cd Tools
python -m unittest discover -s tests -v
python main.py --validate resources/TableTemplate.xlsx
python -m compileall -q main.py uerowforge tests
python tests/gui_smoke.py
```

[개발 규칙](AGENTS.md) · [MIT](LICENSE.txt)
