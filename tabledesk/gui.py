"""Tkinter desktop UI. All project writes require a conversion preview approval."""
from __future__ import annotations
from dataclasses import replace
from datetime import datetime
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import threading
import traceback
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import tkinter.font as tkfont

from . import __version__
from .core import (DEFAULT_HEADER_SUBDIR, DEFAULT_JSON_SUBDIR,
                   Issue, Plan, Project, Registry, Table, ToolError, app_dir, atomic_write,
                   build_plan, discover_projects, execute_plan, inside, json_text, load_tables,
                   modules_for, register_project, relative_dir)
from .unreal_runner import check_engine, resource_root, run_assets
from .code_preview import CodePreview, build_project_code_preview, code_preview_from_plan

BG = "#F2F5F8"
INK = "#172B4D"
MUTED = "#627086"
ACCENT = "#1E66E8"
WHITE = "#FFFFFF"
LINE = "#DCE3EC"


def open_path(path: Path) -> None:
    if not path.exists():
        raise ToolError(f"아직 생성되지 않은 경로입니다: {path}")
    if os.name == "nt":
        os.startfile(str(path))
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)], shell=False)


def configure_style(root: tk.Tk) -> None:
    available = set(tkfont.families())
    family = next((f for f in ("Malgun Gothic", "Apple SD Gothic Neo", "NanumGothic", "Noto Sans CJK KR", "DejaVu Sans") if f in available), "TkDefaultFont")
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
        tkfont.nametofont(name).configure(family=family, size=10)
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", font=(family, 10), background=BG, foreground=INK)
    style.configure("TFrame", background=BG)
    style.configure("Card.TFrame", background=WHITE)
    style.configure("TLabel", background=BG)
    style.configure("Card.TLabel", background=WHITE)
    style.configure("Muted.TLabel", foreground=MUTED)
    style.configure("Title.TLabel", font=(family, 23, "bold"))
    style.configure("Heading.TLabel", font=(family, 13, "bold"))
    style.configure("TButton", padding=(13, 8), borderwidth=1, relief="flat", background=WHITE)
    style.map("TButton", background=[("active", "#E8EFFA"), ("disabled", "#EDF0F5")])
    style.configure("Accent.TButton", background=ACCENT, foreground=WHITE, borderwidth=0)
    style.map("Accent.TButton", background=[("active", "#1654C6"), ("disabled", "#ABB9D0")], foreground=[("disabled", WHITE)])
    style.configure("TEntry", padding=7, fieldbackground=WHITE)
    style.configure("TCombobox", padding=6, fieldbackground=WHITE)
    style.configure("Treeview", background=WHITE, fieldbackground=WHITE, rowheight=33, borderwidth=0)
    style.configure("Treeview.Heading", background="#E9EFF7", font=(family, 10, "bold"), padding=(8, 10), relief="flat")
    style.map("Treeview", background=[("selected", "#E1EBFC")], foreground=[("selected", INK)])
    style.configure("TNotebook", borderwidth=0, background=BG)
    style.configure("TNotebook.Tab", padding=(17, 10), background="#E7EDF5")
    style.map("TNotebook.Tab", background=[("selected", WHITE)])
    root.configure(background=BG)


def text_box(parent, wrap="none", height=10):
    frame = ttk.Frame(parent)
    widget = tk.Text(frame, wrap=wrap, height=height, background=WHITE, foreground=INK,
                     borderwidth=0, padx=14, pady=12, font="TkFixedFont", relief="flat")
    v = ttk.Scrollbar(frame, orient="vertical", command=widget.yview)
    h = ttk.Scrollbar(frame, orient="horizontal", command=widget.xview)
    widget.configure(yscrollcommand=v.set, xscrollcommand=h.set)
    widget.grid(row=0, column=0, sticky="nsew")
    v.grid(row=0, column=1, sticky="ns")
    h.grid(row=1, column=0, sticky="ew")
    frame.rowconfigure(0, weight=1)
    frame.columnconfigure(0, weight=1)
    return frame, widget


def set_text(widget: tk.Text, content: str) -> None:
    widget.configure(state="normal")
    widget.delete("1.0", "end")
    widget.insert("1.0", content)
    widget.configure(state="disabled")


class CodePreviewPanel(ttk.Frame):
    """One tab per actual output file, not one tab per data table."""
    def __init__(self, parent, refresh=None):
        super().__init__(parent, padding=(10, 8))
        self.scope_var = tk.StringVar(value="프로젝트 공통 코드 · 파일 단위 미리보기")
        self.hint_var = tk.StringVar(value="코드는 저장하지 않고 미리보기만 제공합니다.")
        self.tables_var = tk.StringVar(value="(없음)")
        self.path_var = tk.StringVar(value="")
        self.documents = {}
        self.boxes = {}
        self.frames = {}
        top = ttk.Frame(self)
        top.pack(fill="x")
        ttk.Label(top, textvariable=self.scope_var).pack(side="left")
        self.hint_label = ttk.Label(self, textvariable=self.hint_var, style="Muted.TLabel",
                                    wraplength=1020, justify="left")
        self.hint_label.pack(fill="x", pady=(3, 5))
        self.bind("<Configure>", lambda e: self.hint_label.configure(wraplength=max(400, e.width - 24)))
        tablebar = ttk.Frame(self)
        tablebar.pack(fill="x", pady=(0, 5))
        ttk.Label(tablebar, text="포함 테이블", width=12).pack(side="left")
        ttk.Entry(tablebar, textvariable=self.tables_var, state="readonly").pack(side="left", fill="x", expand=True)
        pathbar = ttk.Frame(self)
        pathbar.pack(fill="x", pady=(0, 7))
        ttk.Label(pathbar, text="출력 파일", width=12).pack(side="left")
        ttk.Entry(pathbar, textvariable=self.path_var, state="readonly").pack(side="left", fill="x", expand=True)
        self.copy_button = ttk.Button(pathbar, text="파일 전체 복사", command=self.copy_current, state="disabled")
        self.copy_button.pack(side="right", padx=(8, 0))
        if refresh:
            ttk.Button(pathbar, text="새로 고침", command=refresh).pack(side="right", padx=(8, 0))
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)
        self.notebook.bind("<<NotebookTabChanged>>", lambda e: self.update_path())

    def destroy(self):
        # Explicitly release Tk variables on the UI thread. Destroyed panels can
        # otherwise remain in Python cycles and be finalized by an Excel worker.
        super().destroy()
        for attr in ("scope_var", "hint_var", "tables_var", "path_var"):
            setattr(self, attr, None)
        self.documents.clear()
        self.boxes.clear()
        self.frames.clear()

    def current_path(self):
        selected = self.notebook.select()
        return next((p for p, frame in self.frames.items() if str(frame) == selected), None)

    def update_path(self):
        self.path_var.set(self.current_path() or "")

    def clear(self, message):
        for frame in self.frames.values():
            frame.destroy()
        self.documents.clear()
        self.boxes.clear()
        self.frames.clear()
        self.scope_var.set("공통 코드 미리보기")
        self.hint_var.set(message)
        self.tables_var.set("(없음)")
        self.path_var.set("")
        self.copy_button.configure(state="disabled")

    def show(self, preview: CodePreview, scope: str, hint: str):
        selected = self.current_path()
        documents = {d.relative_path: d for d in preview.documents}
        if list(documents) != list(self.documents):
            self.clear("")
            for path, doc in documents.items():
                frame, box = text_box(self.notebook)
                self.notebook.add(frame, text=doc.filename)
                self.frames[path], self.boxes[path] = frame, box
        for path, doc in documents.items():
            if self.documents.get(path) != doc:
                set_text(self.boxes[path], doc.text)
        self.documents = documents
        self.scope_var.set(scope)
        self.hint_var.set(hint)
        self.tables_var.set(", ".join(preview.included_tables) or "(없음)")
        self.copy_button.configure(state="normal" if documents else "disabled")
        if selected in self.frames:
            self.notebook.select(self.frames[selected])
        self.update_path()

    def copy_current(self):
        doc = self.documents.get(self.current_path())
        if doc:
            self.clipboard_clear()
            self.clipboard_append(doc.text)


class App:
    def __init__(self, root: tk.Tk, registry: Registry | None = None):
        self.root = root
        root.title(f"UE TableDesk · {__version__}")
        root.geometry("1240x860")
        root.minsize(1000, 700)
        configure_style(root)
        self.registry = registry or Registry()
        self.project: Project | None = None
        self.tables: list[Table] = []
        self.file_issues: list[Issue] = []
        self.busy = False
        self.code_preview_dirty = True
        self.events = queue.Queue()
        self.logs: list[str] = []
        self.status = tk.StringVar(value="프로젝트를 등록하거나 샘플로 시작하세요.")
        self.body = ttk.Frame(root, padding=(26, 22))
        self.body.grid(row=0, column=0, sticky="nsew")
        root.rowconfigure(0, weight=1)
        root.columnconfigure(0, weight=1)
        footer = ttk.Frame(root, padding=(26, 9))
        footer.grid(row=1, column=0, sticky="ew")
        self.progress = ttk.Progressbar(footer, mode="indeterminate", length=130)
        self.progress.pack(side="right")
        ttk.Label(footer, textvariable=self.status, style="Muted.TLabel").pack(side="left")
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.bind("<Configure>", self.resize_workspace)
        root.report_callback_exception = self.callback_error
        root.after(100, self.poll)
        self.show_home()

    def resize_workspace(self, event):
        if (event.widget is self.root and hasattr(self, "table_tree")
                and self.table_tree.winfo_exists()):
            rows = 2 if event.height < 780 else 4
            if self.table_tree.cget("height") != rows:
                self.table_tree.configure(height=rows)

    def callback_error(self, typ, value, tb):
        self.log("오류: " + str(value))
        error_dir = self.registry.home
        error_dir.mkdir(parents=True, exist_ok=True)
        with (error_dir / "errors.log").open("a", encoding="utf-8") as f:
            traceback.print_exception(typ, value, tb, file=f)
        messagebox.showerror("오류", str(value), parent=self.root)

    def guard(self):
        if self.busy:
            self.status.set("현재 작업이 진행 중입니다. 작업 종료 전에는 화면/설정을 변경할 수 없습니다.")
            return False
        return True

    def perform(self, fn):
        if not self.guard():
            return
        try:
            return fn()
        except (OSError, ValueError) as exc:
            self.log(str(exc))
            messagebox.showerror("확인 필요", str(exc), parent=self.root)

    def log(self, message):
        line = f"{datetime.now():%H:%M:%S}  {message}"
        self.logs.append(line)
        self.logs = self.logs[-500:]
        if hasattr(self, "log_text") and self.log_text.winfo_exists():
            set_text(self.log_text, "\n".join(self.logs))
            self.log_text.see("end")

    def worker(self, label, operation, callback):
        self.busy = True
        self.status.set(label)
        self.progress.start(12)
        def run():
            try:
                result = operation()
                self.events.put(("done", callback, result))
            except Exception as exc:
                self.events.put(("error", str(exc), traceback.format_exc()))
        threading.Thread(target=run, daemon=True).start()

    def poll(self):
        try:
            while True:
                kind, a, b = self.events.get_nowait()
                if kind == "log":
                    self.log(a)
                    continue
                self.busy = False
                self.progress.stop()
                if kind == "done":
                    a(b)
                else:
                    self.status.set("작업 실패. 로그와 오류 내용을 확인하세요.")
                    self.log(a)
                    messagebox.showerror("작업 실패", a, parent=self.root)
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def clear(self):
        for child in self.body.winfo_children():
            child.destroy()

    def show_home(self):
        if not self.guard():
            return
        self.project = None
        self.clear()
        top = ttk.Frame(self.body)
        top.pack(fill="x", pady=(4, 22))
        ttk.Label(top, text="UE TableDesk", style="Title.TLabel").pack(side="left")
        ttk.Label(top, text=f"PROTOTYPE  {__version__}", style="Muted.TLabel").pack(side="right", pady=(10, 0))
        ttk.Label(self.body, text="엑셀 하나에서 시작해, 여러 언리얼 프로젝트로.", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(self.body, text="프로젝트는 연결만 합니다. 도구를 각 프로젝트에 복사할 필요가 없습니다.", style="Muted.TLabel").pack(anchor="w", pady=(7, 24))
        toolbar = ttk.Frame(self.body)
        toolbar.pack(fill="x", pady=(0, 14))
        ttk.Button(toolbar, text="+  프로젝트 추가", style="Accent.TButton", command=lambda: self.perform(self.add_project)).pack(side="left")
        ttk.Button(toolbar, text="변환 UI 데모", command=lambda: self.perform(self.demo)).pack(side="left", padx=9)
        ttk.Button(toolbar, text="사용 설명서", command=lambda: self.perform(lambda: open_path(resource_root() / "README.md"))).pack(side="right")
        self.project_tree = ttk.Treeview(self.body, columns=("project", "path", "prefix"), show="headings", selectmode="browse")
        for col, label, width in (("project", "프로젝트", 240), ("path", "연결된 프로젝트 폴더", 600), ("prefix", "접두사", 90)):
            self.project_tree.heading(col, text=label, anchor="w")
            self.project_tree.column(col, width=width, anchor="w")
        self.project_tree.pack(fill="both", expand=True)
        for project in self.registry.projects:
            self.project_tree.insert("", "end", iid=project.id, values=(project.name, str(project.root), project.prefix))
        self.project_tree.bind("<Double-1>", lambda e: self.perform(self.open_selected_project))
        bar = ttk.Frame(self.body)
        bar.pack(fill="x", pady=(16, 0))
        ttk.Label(bar, text="등록 해제는 목록만 정리하며, 실제 프로젝트 파일은 삭제하지 않습니다.", style="Muted.TLabel").pack(side="left")
        ttk.Button(bar, text="등록 해제", command=lambda: self.perform(self.unregister)).pack(side="right")
        ttk.Button(bar, text="프로젝트 열기  →", style="Accent.TButton", command=lambda: self.perform(self.open_selected_project)).pack(side="right", padx=9)
        self.status.set(f"등록된 프로젝트 {len(self.registry.projects)}개  ·  Python 표준 라이브러리만 사용")

    def add_project(self):
        folder = filedialog.askdirectory(title=".uproject가 들어 있는 프로젝트 폴더", parent=self.root)
        if not folder:
            return
        choices = discover_projects(Path(folder))
        if len(choices) > 1:
            selected = filedialog.askopenfilename(title="연결할 .uproject 선택", initialdir=folder,
                                                filetypes=[("Unreal Project", "*.uproject")], parent=self.root)
            if not selected:
                return
            if Path(selected).resolve() not in [p.resolve() for p in choices]:
                raise ToolError("선택한 프로젝트 폴더 안의 .uproject를 선택하세요.")
            path = Path(selected)
        else:
            path = choices[0]
        project = self.registry.add(register_project(path))
        self.show_workspace(project)
        if not project.module:
            messagebox.showwarning("C++ 모듈 필요", "프로젝트는 등록했습니다. 변환하려면 이 프로젝트에 C++ 소스 모듈이 필요합니다.", parent=self.root)

    def unregister(self):
        sel = self.project_tree.selection()
        if sel and messagebox.askyesno("등록 해제", "프로그램의 연결 목록에서만 제거합니다. 실제 프로젝트는 그대로 유지됩니다.", parent=self.root):
            self.registry.remove(sel[0])
            self.show_home()

    def open_selected_project(self):
        selection = self.project_tree.selection()
        if selection:
            self.show_workspace(next(p for p in self.registry.projects if p.id == selection[0]))

    def demo(self):
        demo = self.registry.home / "DemoProject"
        source = demo / "Source" / "OperationBreakpoint"
        source.mkdir(parents=True, exist_ok=True)
        uproject = demo / "OperationBreakpoint.uproject"
        if not uproject.exists():
            atomic_write(uproject, json_text({"FileVersion": 3, "TableDeskDemo": True,
                         "Description": "TableDesk conversion-only fixture, not a buildable Unreal project",
                         "Modules": [{"Name": "OperationBreakpoint", "Type": "Runtime"}]}).encode("utf-8"))
            atomic_write(source / "OperationBreakpoint.Build.cs", b"// Conversion-only fixture. NOT a buildable project.\n")
        project = self.registry.add(register_project(uproject))
        sample = str(resource_root() / "Samples" / "TableDeskSample" / "Excel" / "TableTemplate.xlsx")
        # This disposable UI demo always uses the shipped template. Do not keep
        # stale template paths from earlier installations alongside the new one.
        project.sources = [sample]
        self.registry.save()
        self.show_workspace(project)
        self.status.set("샘플 프로젝트: 파일 변환만 테스트합니다. 실제 UE 빌드/에셋 실행은 차단됩니다.")

    def show_workspace(self, project: Project):
        if not self.guard():
            return
        self.project = project
        self.tables = []
        self.file_issues = []
        self.clear()
        top = ttk.Frame(self.body)
        top.pack(fill="x", pady=(0, 8))
        ttk.Button(top, text="←  프로젝트 목록", command=self.show_home).pack(side="left", padx=(0, 18))
        ttk.Label(top, text=project.name, style="Heading.TLabel").pack(side="left")
        ttk.Button(top, text="프로젝트 설정", command=lambda: self.perform(self.settings)).pack(side="right")
        ttk.Label(self.body, text="프로젝트 루트  ·  " + str(project.root) + "   [고정]", style="Muted.TLabel").pack(anchor="w", pady=(2, 16))
        toolbar = ttk.Frame(self.body)
        toolbar.pack(fill="x", pady=(0, 12))
        for text, command in (("+  엑셀 불러오기", self.import_excel), ("다시 읽기 / 검증", self.reload),
                              ("목록 비우기", self.clear_sources), ("템플릿 저장", self.save_template)):
            ttk.Button(toolbar, text=text, command=lambda c=command: self.perform(c)).pack(side="left", padx=(0, 8))
        ttk.Button(toolbar, text="출력 폴더 열기", command=lambda: self.perform(self.open_output)).pack(side="right")
        self.metrics = tk.StringVar(value="엑셀을 불러오면 테이블과 오류가 표시됩니다.")
        ttk.Label(self.body, textvariable=self.metrics, style="Muted.TLabel").pack(anchor="w", pady=(0, 8))
        self.notebook = ttk.Notebook(self.body, height=220)
        self.table_data_frame = ttk.Frame(self.notebook, padding=(8, 7))
        self.notebook.add(self.table_data_frame, text="테이블 데이터 · 개별")
        self.table_tree = ttk.Treeview(self.table_data_frame, columns=("name", "source", "rows", "status", "path"),
                                       show="headings", selectmode="extended", height=2 if self.root.winfo_height() < 780 else 4)
        for col, label, width in (("name", "테이블", 160), ("source", "원본 파일 / 시트", 320), ("rows", "행", 70),
                                   ("status", "검증", 90), ("path", "추가 하위 경로", 220)):
            self.table_tree.heading(col, text=label, anchor="w")
            self.table_tree.column(col, width=width, anchor="w", stretch=col not in ("rows", "status"))
        self.table_tree.tag_configure("error", foreground="#AD3434")
        self.table_tree.pack(fill="x")
        self.table_tree.bind("<<TreeviewSelect>>", lambda e: self.preview_table())
        routebar = ttk.Frame(self.table_data_frame)
        routebar.pack(fill="x", pady=(9, 12))
        ttk.Button(routebar, text="정상 테이블 전체 선택", command=self.select_valid).pack(side="left")
        ttk.Button(routebar, text="선택 테이블 경로 지정", command=lambda: self.perform(self.edit_route)).pack(side="left", padx=8)
        ttk.Label(routebar, text="Ctrl / Shift로 여러 테이블 선택", style="Muted.TLabel").pack(side="right")
        self.data_hint = tk.StringVar(value="목록에서 테이블을 선택하세요. 데이터·JSON만 선택한 테이블을 보여줍니다.")
        ttk.Label(self.table_data_frame, textvariable=self.data_hint, style="Muted.TLabel").pack(anchor="w", pady=(0, 7))
        self.data_notebook = ttk.Notebook(self.table_data_frame)
        self.data_notebook.pack(fill="both", expand=True)
        data_frame = ttk.Frame(self.data_notebook)
        self.data_notebook.add(data_frame, text="데이터")
        self.data_tree = ttk.Treeview(data_frame, show="headings", height=5)
        vs = ttk.Scrollbar(data_frame, orient="vertical", command=self.data_tree.yview)
        hs = ttk.Scrollbar(data_frame, orient="horizontal", command=self.data_tree.xview)
        self.data_tree.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        self.data_tree.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        hs.grid(row=1, column=0, sticky="ew")
        data_frame.rowconfigure(0, weight=1)
        data_frame.columnconfigure(0, weight=1)
        self.json_frame, self.json_text = text_box(self.data_notebook)
        self.data_notebook.add(self.json_frame, text="JSON")
        self.code_panel = CodePreviewPanel(self.notebook, refresh=lambda: self.perform(lambda: self.refresh_code_preview(force=True)))
        self.notebook.add(self.code_panel, text="프로젝트 코드 · 전체")
        for attr, label in (("issues_text", "검증 결과"), ("log_text", "실행 로그")):
            frame, text = text_box(self.notebook)
            setattr(self, attr, text)
            setattr(self, "issues_frame" if attr == "issues_text" else "log_frame", frame)
            self.notebook.add(frame, text=label)
            set_text(text, "")
        set_text(self.log_text, "\n".join(self.logs))
        self.code_preview_dirty = True
        self.notebook.bind("<<NotebookTabChanged>>", self.preview_tab_changed)
        bottom = ttk.Frame(self.body)
        bottom.pack(side="bottom", fill="x", pady=(14, 0))
        ttk.Label(bottom, text="변환: JSON·행 구조체·서브시스템 코드  /  에셋 반영: 별도 실행", style="Muted.TLabel").pack(side="left")
        ttk.Button(bottom, text="UE 에셋 반영 (실험)", command=lambda: self.perform(self.apply_assets)).pack(side="right")
        self.convert_label = tk.StringVar(value="선택 항목 변환 (0)  →")
        self.convert_button = ttk.Button(bottom, textvariable=self.convert_label, style="Accent.TButton",
                                         command=lambda: self.perform(self.convert), state="disabled")
        self.convert_button.pack(side="right", padx=8)
        self.notebook.pack(fill="both", expand=True)
        if project.sources:
            self.reload()
        else:
            self.preview_table()
            self.status.set("엑셀을 추가하고 프로젝트 설정에서 접두사와 출력 경로를 지정하세요.")

    def import_excel(self):
        selected = filedialog.askopenfilenames(title="변환할 Excel 파일", filetypes=[("Excel workbook", "*.xlsx")], parent=self.root)
        if not selected:
            return
        assert self.project
        self.project.sources = list(dict.fromkeys(self.project.sources + list(selected)))
        self.registry.save()
        self.reload()

    def reload(self):
        if not self.guard() or not self.project:
            return
        paths = list(map(Path, self.project.sources))
        self.worker("엑셀을 읽고 입력값을 검증하는 중…", lambda: load_tables(paths), self.loaded)

    def loaded(self, result):
        self.tables, self.file_issues = result
        self.table_tree.delete(*self.table_tree.get_children())
        for i, table in enumerate(self.tables):
            errors = sum(x.level == "오류" for x in table.issues)
            self.table_tree.insert("", "end", iid=str(i), values=(table.name, f"{Path(table.source).name} / {table.sheet}",
                                  len(table.rows), f"오류 {errors}" if errors else "정상", self.project.route_for(table) or "(없음)"),
                                  tags=("error",) if errors else ())
        all_issues = self.file_issues + [i for t in self.tables for i in t.issues]
        set_text(self.issues_text, "\n".join(map(str, all_issues)) or "모든 테이블이 입력 형식 검증을 통과했습니다.\n미리보기 데이터는 최대 200행입니다.")
        self.metrics.set(f"원본 {len(self.project.sources)}개   /   테이블 {len(self.tables)}개   /   정상 {sum(t.valid for t in self.tables)}개   /   오류 {len(all_issues)}건")
        self.select_valid()
        if not self.table_tree.selection() and self.tables:
            self.table_tree.selection_set("0")
        self.preview_table()
        self.status.set("검증 완료. 테이블을 선택하고 변환 경로·변경점을 확인하세요.")
        self.log(f"불러오기 완료: 테이블 {len(self.tables)}개, 오류 {len(all_issues)}건")
        if all_issues:
            self.notebook.select(self.issues_frame)
        self.invalidate_code_preview()

    def clear_sources(self):
        if not self.project:
            return
        self.project.sources = []
        self.registry.save()
        self.loaded(([], []))
        self.preview_table()

    def select_valid(self):
        if self.busy:
            return
        valid = [str(i) for i, t in enumerate(self.tables) if t.valid]
        self.table_tree.selection_set(valid)
        if valid:
            self.table_tree.focus(valid[0])

    def selected_tables(self):
        selected = [self.tables[int(i)] for i in self.table_tree.selection()]
        if not selected:
            raise ToolError("변환할 테이블을 선택하세요.")
        return selected

    def preview_table(self):
        """Only data and JSON follow table selection. Never rebuild code here."""
        if not hasattr(self, "table_tree") or not self.table_tree.winfo_exists():
            return
        selection = self.table_tree.selection()
        self.convert_label.set(f"선택 항목 변환 ({len(selection)})  →")
        self.convert_button.configure(state="normal" if selection else "disabled")
        self.data_tree.delete(*self.data_tree.get_children())
        if not selection or not self.project:
            self.data_tree.configure(columns=())
            self.data_hint.set("목록에서 테이블을 선택하세요. 공통 코드는 선택 없이도 볼 수 있습니다.")
            self.data_notebook.tab(self.json_frame, text="JSON")
            set_text(self.json_text, "테이블을 선택하세요.")
            return
        # For multiselection, use the focused row instead of always showing the
        # first selected row. Programmatic selection falls back to the first.
        focus = self.table_tree.focus()
        table = self.tables[int(focus if focus in selection else selection[0])]
        self.data_hint.set(f"현재 테이블: {table.name}  ·  데이터 {len(table.rows)}행  ·  변환 선택 {len(selection)}개 / 개별 미리보기 1개")
        self.data_notebook.tab(self.json_frame, text=f"{table.name}.json")
        columns = [f"c{i}" for i in range(len(table.fields))]
        self.data_tree.configure(columns=columns)
        for col, fld in zip(columns, table.fields):
            self.data_tree.heading(col, text=f"{fld.name}  ·  {fld.type}", anchor="w")
            self.data_tree.column(col, width=165, minwidth=100, stretch=False)
        for row in table.rows[:200]:
            values = [str(row.get(f.name, "<오류>"))[:500] for f in table.fields]
            self.data_tree.insert("", "end", values=values)
        if table.valid:
            set_text(self.json_text, json_text(table.rows[:200]) + ("\n// 미리보기는 200행까지. 출력은 전체 행입니다." if len(table.rows) > 200 else ""))
        else:
            set_text(self.json_text, "검증 오류가 있어 JSON 생성을 차단했습니다. 검증 결과 탭을 확인하세요.")

    def preview_tab_changed(self, event=None):
        if self.notebook.select() == str(self.code_panel):
            # Recheck disk state when reopening the common code tab; do not
            # rescan the project on ordinary table selection events.
            self.refresh_code_preview(force=True)

    def invalidate_code_preview(self):
        self.code_preview_dirty = True
        if (hasattr(self, "code_panel") and self.code_panel.winfo_exists()
                and self.notebook.select() == str(self.code_panel)):
            self.refresh_code_preview()

    def refresh_code_preview(self, *, force=False):
        if not self.project or not self.code_panel.winfo_exists():
            return
        if self.busy:
            self.code_preview_dirty = True
            return
        if not force and not self.code_preview_dirty:
            return
        self.code_preview_dirty = False
        try:
            preview = build_project_code_preview(self.project, self.tables)
            scope = (f"공통 코드 예상 결과 · 불러온 정상 {len(preview.incoming_tables)}개"
                     f" + 기존 보존 {len(preview.retained_tables)}개")
            hint = "테이블 선택과 무관한 전체입니다. 선택 항목만 변환할 때의 결과는 [변환 전 변경점 확인]에서 확인하세요."
            if preview.excluded_tables:
                hint += "\n오류 테이블 제외(기존 생성본이 있으면 보존): " + ", ".join(preview.excluded_tables)
            if self.file_issues:
                hint += f"\n원본 읽기 오류 {len(self.file_issues)}건: 참고용 미리보기이며 실제 변환은 차단됩니다."
            if not preview.documents:
                hint = "아직 표시할 코드가 없습니다. 정상 테이블을 불러오면 3개 공통 파일 전체를 미리 볼 수 있습니다." + ("\n" + hint if preview.excluded_tables or self.file_issues else "")
            self.code_panel.show(preview, scope, hint)
        except (OSError, ValueError) as exc:
            # Do not leave an old valid-looking result visible after a failure.
            self.code_panel.clear("미리보기 차단 (파일은 변경하지 않았습니다):\n" + str(exc))

    def settings(self):
        assert self.project
        project = self.project
        win = tk.Toplevel(self.root)
        win.title("프로젝트 설정")
        win.geometry("900x740")
        win.transient(self.root)
        win.grab_set()
        frame = ttk.Frame(win, padding=24)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="프로젝트별 출력 설정", style="Heading.TLabel").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 18))
        ttk.Label(frame, text="프로젝트 루트").grid(row=1, column=0, sticky="w", pady=6)
        root_var = tk.StringVar(value=str(project.root))
        win.project_root_var = root_var  # Keep the readonly value alive after this method returns.
        ttk.Entry(frame, textvariable=root_var, state="readonly").grid(row=1, column=1, columnspan=2, sticky="ew", pady=6)
        labels = [("module", "대상 C++ 모듈"), ("prefix", "코드 접두사"), ("header_subdir", "헤더 하위 경로"),
                  ("json_subdir", "JSON 기본 폴더"), ("asset_subdir", "에셋 하위 경로"), ("engine_cmd", "UE 실행파일 (선택)")]
        variables = {}
        for row, (key, label) in enumerate(labels, 2):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=6, padx=(0, 16))
            var = tk.StringVar(value=getattr(project, key))
            variables[key] = var
            if key == "module":
                widget = ttk.Combobox(frame, values=modules_for(Path(project.uproject)), state="readonly", textvariable=var)
            else:
                widget = ttk.Entry(frame, textvariable=var)
            widget.grid(row=row, column=1, sticky="ew", pady=6)
            if key == "engine_cmd":
                def browse():
                    path = filedialog.askopenfilename(title="UnrealEditor-Cmd.exe", filetypes=[("Unreal Editor", "UnrealEditor-Cmd.exe"), ("All", "*")], parent=win)
                    if path:
                        variables["engine_cmd"].set(path)
                ttk.Button(frame, text="찾기", command=browse).grid(row=row, column=2, padx=(8, 0))
        help_text = ("헤더 기준: [프로젝트]/Source/[모듈]/Public/ + 헤더 하위 경로\n"
                     "JSON 기준: [프로젝트]/ + JSON 기본 폴더 + 테이블 추가 경로\n"
                     "에셋 기준: [프로젝트]/Content/ + 에셋 하위 경로 + 테이블 추가 경로\n\n"
                     "기본값: 헤더 Public/Data · JSON 프로젝트/DataTable · 추가 하위 경로 없음\n"
                     "예: 접두사 OB → OBStructTypes.h / FOBPlayersRow\n"
                     "관리 클래스는 UDataTableSubsystem 고정. .cpp는 Private/동일 하위 경로에 생성합니다.\n"
                     "테이블 접근: private 변수 + public Get<Table>Table() / C++·BP 공용\n"
                     "행 필드: BlueprintReadOnly + Category 고정. 수기 코드와 충돌하면 중단합니다.\n"
                     "접두사·경로 변경은 기존 파일/타입/에셋을 자동 이동하거나 삭제하지 않습니다.")
        ttk.Label(frame, text=help_text, style="Muted.TLabel", justify="left").grid(row=8, column=0, columnspan=3, sticky="w", pady=18)
        frame.columnconfigure(1, weight=1)
        # Applying defaults is explicit: an update must not silently reroute
        # existing projects or discard the user's custom output locations.
        reset_routes = None
        reset_note = tk.StringVar(value="기본 경로 적용: 헤더·JSON 경로와 불러온/저장된 테이블의 추가 경로를 초기화합니다.")
        ttk.Label(frame, textvariable=reset_note, style="Muted.TLabel", wraplength=810,
                  justify="left").grid(row=9, column=0, columnspan=3, sticky="w", pady=(0, 12))
        buttons = ttk.Frame(frame)
        buttons.grid(row=10, column=0, columnspan=3, sticky="ew")
        def apply_defaults():
            nonlocal reset_routes
            variables["header_subdir"].set(DEFAULT_HEADER_SUBDIR)
            variables["json_subdir"].set(DEFAULT_JSON_SUBDIR)
            names = set(project.routes) | {table.name for table in self.tables}
            # Explicit empty overrides also clear SubPath from older templates.
            # Do not use dict.clear(): that would reactivate Excel's SubPath.
            reset_routes = {name: "" for name in sorted(names)}
            reset_note.set("기본 경로를 입력했습니다. 추가 경로는 빈 값으로 저장됩니다. [설정 저장]을 눌러 반영하세요.")
        ttk.Button(buttons, text="기본 경로 적용", command=apply_defaults).pack(side="left")
        def save():
            try:
                values = {k: v.get().strip() for k, v in variables.items()}
                for key in ("header_subdir", "json_subdir", "asset_subdir"):
                    values[key] = relative_dir(values[key], unreal=key != "json_subdir")
                candidate = replace(project, **values,
                                    routes=dict(project.routes) if reset_routes is None else reset_routes)
                candidate.check()
                # Restore in-memory settings too if registry persistence fails.
                previous = {key: getattr(project, key) for key in (*variables, "routes")}
                try:
                    for key in previous:
                        setattr(project, key, getattr(candidate, key))
                    self.registry.save()
                except (ValueError, OSError):
                    for key, value in previous.items():
                        setattr(project, key, value)
                    raise
                win.destroy()
                for i, table in enumerate(self.tables):
                    self.table_tree.set(str(i), "path", project.route_for(table) or "(없음)")
                self.preview_table()
                self.invalidate_code_preview()
                self.log("프로젝트 설정 저장" + (" · 기본 경로 적용, 추가 경로 비움" if reset_routes is not None else ""))
            except (ValueError, OSError) as exc:
                messagebox.showerror("설정 확인", str(exc), parent=win)
        ttk.Button(buttons, text="설정 저장", style="Accent.TButton", command=save).pack(side="right")
        ttk.Button(buttons, text="취소", command=win.destroy).pack(side="right", padx=8)

    def edit_route(self):
        tables = self.selected_tables()
        assert self.project
        win = tk.Toplevel(self.root)
        win.title("선택 테이블 하위 경로")
        win.geometry("650x260")
        win.transient(self.root)
        win.grab_set()
        frame = ttk.Frame(win, padding=24)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=", ".join(t.name for t in tables), style="Heading.TLabel").pack(anchor="w")
        ttk.Label(frame, text="추가 하위 경로는 기본적으로 비워 둡니다. 폴더를 나눌 때만 입력하세요.", style="Muted.TLabel").pack(anchor="w", pady=(12, 10))
        var = tk.StringVar(value=self.project.route_for(tables[0]))
        entry_row = ttk.Frame(frame)
        entry_row.pack(fill="x")
        ttk.Entry(entry_row, textvariable=var).pack(side="left", fill="x", expand=True)
        ttk.Button(entry_row, text="비우기", command=lambda: var.set("")).pack(side="right", padx=(8, 0))
        ttk.Label(frame, text="빈 칸으로 저장하면 프로젝트 기본 폴더에 바로 출력합니다. 엑셀 SubPath보다 이 설정이 우선합니다.", style="Muted.TLabel", wraplength=590).pack(anchor="w", pady=10)
        def save():
            try:
                route = relative_dir(var.get(), unreal=True)
                for table in tables:
                    self.project.routes[table.name] = route
                self.registry.save()
                for i, table in enumerate(self.tables):
                    self.table_tree.set(str(i), "path", self.project.route_for(table) or "(없음)")
                win.destroy()
                self.invalidate_code_preview()
            except (OSError, ValueError) as exc:
                messagebox.showerror("경로 확인", str(exc), parent=win)
        ttk.Button(frame, text="저장", style="Accent.TButton", command=save).pack(anchor="e")

    def save_template(self):
        path = filedialog.asksaveasfilename(title="엑셀 템플릿 저장", defaultextension=".xlsx", initialfile="TableTemplate.xlsx",
                                          filetypes=[("Excel workbook", "*.xlsx")], parent=self.root)
        if path:
            source = resource_root() / "Samples" / "TableDeskSample" / "Excel" / "TableTemplate.xlsx"
            if Path(path).resolve() == source.resolve():
                return
            shutil.copyfile(source, path)
            self.log("템플릿 저장: " + path)

    def open_output(self):
        assert self.project
        path = inside(self.project.root, self.project.json_subdir)
        open_path(path if path.exists() else self.project.root)

    def convert(self):
        assert self.project
        if self.file_issues:
            raise ToolError("불러오지 못한 원본 파일이 있습니다. 검증 결과를 확인하거나 목록을 비우고 다시 불러오세요.")
        plan = build_plan(self.project, self.selected_tables())
        self.plan_dialog(plan)

    def plan_dialog(self, plan: Plan):
        win = tk.Toplevel(self.root)
        win.title("변환 전 변경점 확인")
        win.geometry("1050x710")
        win.transient(self.root)
        win.grab_set()
        frame = ttk.Frame(win, padding=22)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="실제 파일을 쓰기 전에 확인하세요", style="Heading.TLabel").pack(anchor="w", pady=(0, 12))
        note = ttk.Notebook(frame)
        note.pack(fill="both", expand=True)
        for label, contents in (("출력 계획", plan.summary()), ("C++ 변경점", plan.code_diff())):
            panel, box = text_box(note)
            note.add(panel, text=label)
            set_text(box, contents)
        code_panel = CodePreviewPanel(note)
        preview = code_preview_from_plan(plan)
        code_panel.show(preview,
                        f"이번 변환의 실제 코드 · 선택 {len(preview.incoming_tables)}개 + 기존 보존 {len(preview.retained_tables)}개",
                        "아래는 이번에 저장할 3개 코드 파일 전체입니다. 미선택 신규 테이블은 포함하지 않습니다.")
        note.add(code_panel, text="생성 코드 전체")
        win.code_panel = code_panel
        bottom = ttk.Frame(frame)
        bottom.pack(fill="x", pady=(15, 0))
        ttk.Label(bottom, text="변경될 기존 파일은 Saved/TableDesk/Backups에 먼저 백업합니다.", style="Muted.TLabel").pack(side="left")
        ttk.Button(bottom, text="취소", command=win.destroy).pack(side="right")
        def go():
            win.destroy()
            self.worker("JSON·행 구조체·서브시스템 코드 생성 중…", lambda: execute_plan(plan), lambda backup: self.converted(plan, backup))
        ttk.Button(bottom, text=f"{len(plan.changed)}개 파일 생성·갱신", style="Accent.TButton", command=go).pack(side="right", padx=9)

    def converted(self, plan: Plan, backup):
        plan.project.last_conversion = datetime.now().isoformat(timespec="seconds")
        self.registry.save()
        suffix = "C++ 코드 변경: 에셋 반영 전에 Editor 타깃 전체 빌드가 필요합니다." if plan.code_changed else "C++ 코드 변경 없음."
        self.log(f"변환 완료: {len(plan.tables)}개 테이블, {len(plan.changed)}개 파일. {suffix}")
        if backup:
            self.log("백업: " + str(backup))
        self.status.set("변환 완료 · " + suffix)
        self.invalidate_code_preview()
        self.notebook.select(self.log_frame)
        messagebox.showinfo("파일 변환 완료", f"JSON·행 구조체·DataTableSubsystem.h/.cpp 생성/갱신을 완료했습니다.\n{suffix}\n\n"
                            ".uasset은 아직 생성하지 않았습니다. UE 에셋 반영 버튼은 별도 단계입니다.", parent=self.root)

    def apply_assets(self):
        assert self.project
        plan = build_plan(self.project, self.selected_tables())
        check_engine(plan)
        message = ("실험 기능: 실제 UE 환경에서 이 배포본의 연동 실행은 아직 검증하지 못했습니다.\n\n"
                   "1. 행 구조체·서브시스템(.h/.cpp)을 포함한 C++ Editor 타깃 전체 빌드를 완료했습니까?\n"
                   "2. 이 프로젝트를 연 모든 언리얼 에디터를 종료했습니까?\n"
                   "3. Python Editor Script Plugin / Editor Scripting Utilities를 켰습니까?\n\n"
                   "선택한 에셋을 생성하거나 데이터를 교체하고 저장합니다. 기존 에셋은 파일 백업합니다.\n"
                   "모두 성공하면 Config/DefaultGame.ini의 TableDesk 전용 구역에 경로를 자동 등록합니다.\n"
                   "쿠킹 설정은 자동 변경하지 않습니다. 패키징 전 테이블 폴더의 포함 여부를 확인하세요.\n"
                   "여러 에셋 저장 중 실패하면 일부 에셋만 반영될 수 있습니다. 프로젝트 복사본에서 먼저 시험하세요.\n\n"
                   "위 내용을 확인했고 실행하겠습니까?")
        if not messagebox.askyesno("UE 에셋 반영 확인", message, parent=self.root):
            return
        self.notebook.select(self.log_frame)
        self.worker("언리얼 에셋 반영 중… (프로젝트를 열지 마세요)",
                    lambda: run_assets(plan, lambda s: self.events.put(("log", s, None))), self.assets_done)

    def assets_done(self, result):
        self.log("에셋 반영 완료: " + ", ".join(result["saved"]))
        self.status.set(f"에셋 {len(result['saved'])}개 저장 완료")
        messagebox.showinfo("UE 에셋 반영", "저장 완료:\n" + "\n".join(result["saved"]) + "\n\n런타임 등록: " + result.get("registration_path", "")
                            + "\n다음 게임 실행부터 로드됩니다. 쿠킹 포함 설정은 별도로 확인하세요.", parent=self.root)

    def close(self):
        if self.busy:
            messagebox.showwarning("작업 진행 중", "파일/에셋 저장 작업 중에는 앱을 종료하지 않습니다. 작업 결과를 확인한 뒤 종료하세요.", parent=self.root)
            return
        self.root.destroy()


def launch(demo=False):
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (OSError, AttributeError):
            pass
    root = tk.Tk()
    try:
        app = App(root)
        if demo:
            root.after(100, lambda: app.perform(app.demo))
        root.mainloop()
    except Exception as exc:
        messagebox.showerror("UE TableDesk 시작 실패", str(exc), parent=root)
        root.destroy()
        raise
