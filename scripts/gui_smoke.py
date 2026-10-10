"""Developer-only GUI smoke test. Requires a display; optional PIL for screenshots."""
from pathlib import Path
import os
import sys
import tempfile
import time
import tkinter as tk
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tabledesk.gui import App
from tabledesk.core import Registry, build_plan, execute_plan


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


def click(dialog, text):
    matches = [widget for widget in descendants(dialog)
               if widget.winfo_class() == "TButton" and widget.cget("text") == text]
    assert len(matches) == 1, (text, matches)
    matches[0].invoke()


def current_dialog(root):
    dialogs = [widget for widget in root.winfo_children() if isinstance(widget, tk.Toplevel)]
    assert len(dialogs) == 1
    return dialogs[0]


def main():
    with tempfile.TemporaryDirectory() as tmp:
        registry = Registry(Path(tmp))
        root = tk.Tk()
        app = App(root, registry)
        errors = []
        with patch('tabledesk.gui.messagebox.showerror', side_effect=lambda *a, **k: errors.append(a)), \
             patch('tabledesk.gui.messagebox.showinfo', return_value=None):
            root.update()
            app.demo()
            limit = time.monotonic() + 10
            while app.busy and time.monotonic() < limit:
                root.update()
                time.sleep(0.03)
            root.update()
            assert not app.busy, "Excel load did not finish"
            assert len(app.tables) == 2
            assert len(app.table_tree.get_children()) == 2
            assert len(app.data_tree.get_children()) == 3
            assert len(app.table_tree.selection()) == 2
            assert not errors, errors
            # Data and JSON remain table-specific, while common code is never
            # tied to the selected row or selected conversion subset.
            assert [app.notebook.tab(t, "text") for t in app.notebook.tabs()] == [
                "테이블 데이터 · 개별", "프로젝트 코드 · 전체", "검증 결과", "실행 로그"]
            app.notebook.select(app.code_panel)
            root.update()
            documents = {d.filename: d for d in app.code_panel.documents.values()}
            assert set(documents) == {"OBStructTypes.h", "DataTableSubsystem.h", "DataTableSubsystem.cpp"}
            assert "BlueprintReadOnly" in documents["OBStructTypes.h"].text
            assert "BlueprintReadWrite" not in documents["OBStructTypes.h"].text
            preview = "\n".join(d.text for d in documents.values())
            assert "UDataTableSubsystem" in preview
            assert "TObjectPtr<UDataTable> PlayersTable" in preview
            assert "TMap" not in preview
            assert "UDataTable* GetPlayersTable() const" in preview
            assert "UDataTable* GetItemsTable() const" in preview
            assert "UFUNCTION(BlueprintPure" in preview
            assert "const UScriptStruct* ExpectedRowStruct" in preview
            assert "template <" not in preview
            assert "TryGetPlayersRow" not in preview
            assert "FindPlayersRow" not in preview
            assert "#pragma once" in documents["OBStructTypes.h"].text
            assert "FOBItemsRow :" in documents["OBStructTypes.h"].text
            assert "FOBPlayersRow :" in documents["OBStructTypes.h"].text
            assert app.code_panel.tables_var.get() == "Items, Players"
            root.geometry("1000x700")
            root.update()
            assert next(iter(app.code_panel.boxes.values())).winfo_height() >= 140
            assert app.convert_button.winfo_viewable()
            app.notebook.select(app.table_data_frame)
            root.update()
            assert app.data_tree.winfo_height() >= 50
            root.geometry("1240x860")
            app.notebook.select(app.code_panel)
            root.update()
            before_documents = dict(app.code_panel.documents)
            assert not (app.project.root / "DataTable").exists(), "Preview must not write files"
            with patch('tabledesk.gui.build_project_code_preview', side_effect=AssertionError("Selection must not rebuild code")):
                for index in ("0", "1"):
                    app.table_tree.selection_set(index)
                    app.table_tree.focus(index)
                    root.update()
                    assert app.code_panel.documents == before_documents
                    assert app.tables[int(index)].name in app.data_hint.get()
                    assert app.data_notebook.tab(app.json_frame, "text") == app.tables[int(index)].name + ".json"
                app.table_tree.selection_remove(*app.table_tree.selection())
                root.update()
                assert app.code_panel.documents == before_documents
                assert "테이블을 선택" in app.json_text.get("1.0", "end")
            # Copy copies one actual file, without path banners or concatenation.
            app.code_panel.copy_current()
            assert root.clipboard_get() == app.code_panel.documents[app.code_panel.current_path()].text
            assert all(box.cget("state") == "disabled" for box in app.code_panel.boxes.values())
            # The final confirmation has its own exact selection-based full files.
            app.table_tree.selection_set("0")
            app.plan_dialog(build_plan(app.project, app.selected_tables()))
            root.update()
            dialog = current_dialog(root)
            assert dialog.code_panel.tables_var.get() == app.tables[0].name
            only = "\n".join(d.text for d in dialog.code_panel.documents.values())
            assert "FOBItemsRow" not in only
            assert "FOBPlayersRow" in only
            click(dialog, "취소")
            app.select_valid()
            app.notebook.select(app.table_data_frame)
            root.update()
            assert app.project.header_subdir == "Data"
            assert app.project.json_subdir == "DataTable"
            assert all(app.project.route_for(t) == "" for t in app.tables)
            assert all(app.table_tree.set(str(i), "path") == "(없음)" for i in range(2))
            # Simulate saved v0.1.0 paths and the old template's prefilled routes.
            app.project.header_subdir = "Data/Generated"
            app.project.json_subdir = "DataSource/DataTables"
            app.project.routes = {"Players": "Custom", "StoredTable": "PreviouslySet"}
            app.tables[0].subpath = "Characters"
            app.tables[1].subpath = "Items"
            app.registry.save()
            app.settings()
            dialog = current_dialog(root)
            readonly = [w for w in descendants(dialog)
                        if w.winfo_class() == "TEntry" and str(w.cget("state")) == "readonly"]
            assert len(readonly) == 1 and readonly[0].get() == str(app.project.root)
            click(dialog, "기본 경로 적용")
            click(dialog, "취소")
            assert app.project.json_subdir == "DataSource/DataTables"
            assert app.project.routes["Players"] == "Custom"
            # Reset only commits after Save; explicit empty routes beat old Excel.
            app.settings()
            dialog = current_dialog(root)
            click(dialog, "기본 경로 적용")
            click(dialog, "설정 저장")
            assert app.project.header_subdir == "Data"
            assert app.project.json_subdir == "DataTable"
            assert app.project.asset_subdir == "DataTables"
            assert app.project.prefix == "OB"
            assert app.project.routes == {"Players": "", "Items": "", "StoredTable": ""}
            assert Registry(registry.home).projects[0].routes == app.project.routes
            assert all(app.table_tree.set(str(i), "path") == "(없음)" for i in range(2))
            # User subfolder entry still works; the Clear button persists an empty
            # override instead of falling back to the legacy Excel SubPath.
            app.table_tree.selection_set("0")
            app.edit_route()
            dialog = current_dialog(root)
            entry = next(w for w in descendants(dialog) if w.winfo_class() == "TEntry")
            entry.delete(0, "end")
            entry.insert(0, "Characters")
            click(dialog, "저장")
            assert app.project.route_for(app.tables[0]) == "Characters"
            app.edit_route()
            dialog = current_dialog(root)
            click(dialog, "비우기")
            click(dialog, "저장")
            assert app.project.route_for(app.tables[0]) == ""
            app.select_valid()
            assert not errors, errors
            # Test all primary dialogs: settings, per-table path and preview.
            for operation in (app.settings, app.edit_route, lambda: app.plan_dialog(build_plan(app.project, app.selected_tables()))):
                operation()
                root.update()
                dialogs = [c for c in root.winfo_children() if isinstance(c, tk.Toplevel)]
                assert dialogs
                for dialog in dialogs:
                    dialog.destroy()
                root.update()
            plan = build_plan(app.project, app.selected_tables())
            app.plan_dialog(plan)
            root.update()
            dialog = current_dialog(root)
            click(dialog, f"{len(plan.changed)}개 파일 생성·갱신")
            limit = time.monotonic() + 10
            while app.busy and time.monotonic() < limit:
                root.update()
                time.sleep(0.03)
            assert not app.busy and not errors, errors
            assert (app.project.root / "DataTable/Players.json").is_file()
            assert (app.project.root / "DataTable/Items.json").is_file()
            assert (app.project.root / "Source/OperationBreakpoint/Public/Data/OBStructTypes.h").is_file()
            assert (app.project.root / app.project.subsystem_header_relative).is_file()
            assert (app.project.root / app.project.subsystem_source_relative).is_file()
            assert not (app.project.root / "Config/DefaultGame.ini").exists()
            assert not build_plan(app.project, app.selected_tables()).changed
            root.update()
            # Opening common code without table selection still shows both files'
            # table sets, and clearing inputs retains tracked code without writes.
            before_paths = {p.relative_to(app.project.root).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
                            for p in app.project.root.rglob("*") if p.is_file()}
            app.clear_sources()
            root.update()
            app.notebook.select(app.code_panel)
            root.update()
            assert app.code_panel.tables_var.get() == "Items, Players"
            assert "기존 보존 2개" in app.code_panel.scope_var.get()
            after_paths = {p.relative_to(app.project.root).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
                           for p in app.project.root.rglob("*") if p.is_file()}
            assert before_paths == after_paths
            # Broken source/managed state clears old output instead of displaying
            # a previously valid-looking whole-file preview.
            hpath = app.project.root / app.project.subsystem_header_relative
            original = hpath.read_bytes()
            hpath.write_bytes(original + b"\n// external edit\n")
            app.refresh_code_preview(force=True)
            assert not app.code_panel.documents
            assert "미리보기 차단" in app.code_panel.hint_var.get()
            assert str(app.code_panel.copy_button.cget("state")) == "disabled"
            hpath.write_bytes(original)
            app.refresh_code_preview(force=True)
            assert len(app.code_panel.documents) == 3
            # Old installs used examples/TableTemplate.xlsx. Opening the demo
            # must replace stale paths, not keep two conflicting templates.
            app.project.sources = [str(Path(tmp) / "old-install/examples/TableTemplate.xlsx")]
            registry.save()
            # Restore sample rows, then capture the actual running UI if asked.
            app.demo()
            limit = time.monotonic() + 10
            while app.busy and time.monotonic() < limit:
                root.update()
                time.sleep(0.03)
            root.update()
            assert not app.busy and not errors, errors
            assert app.project.sources == [str(ROOT / "Samples/TableDeskSample/Excel/TableTemplate.xlsx")]
            shot_dir = os.environ.get("TABLEDESK_SCREENSHOTS")
            if shot_dir:
                from PIL import ImageGrab
                shot_dir = Path(shot_dir)
                shot_dir.mkdir(parents=True, exist_ok=True)
                app.notebook.select(app.table_data_frame)
                app.status.set("샘플 검증 완료 · 데이터/JSON은 개별, C++ 코드는 프로젝트 전체")
                root.update()
                time.sleep(0.15)
                box = (root.winfo_rootx(), root.winfo_rooty(), root.winfo_rootx()+root.winfo_width(), root.winfo_rooty()+root.winfo_height())
                ImageGrab.grab(bbox=box).save(shot_dir / "workspace.png")
                app.notebook.select(app.code_panel)
                root.update()
                # One selected table, but the common file includes both schemas.
                app.table_tree.selection_set("0")
                root.update()
                app.code_panel.boxes[app.project.header_relative].yview("10.0")
                root.update()
                time.sleep(0.15)
                ImageGrab.grab(bbox=box).save(shot_dir / "code_preview.png")
                app.code_panel.notebook.select(app.code_panel.frames[app.project.subsystem_header_relative])
                root.update()
                app.code_panel.boxes[app.project.subsystem_header_relative].yview("16.0")
                root.update()
                time.sleep(0.15)
                ImageGrab.grab(bbox=box).save(shot_dir / "subsystem.png")
                app.code_panel.notebook.select(app.code_panel.frames[app.project.subsystem_source_relative])
                root.update()
                ImageGrab.grab(bbox=box).save(shot_dir / "subsystem_cpp.png")
                app.settings()
                root.update()
                dialog = current_dialog(root)
                dbox = (dialog.winfo_rootx(), dialog.winfo_rooty(), dialog.winfo_rootx()+dialog.winfo_width(), dialog.winfo_rooty()+dialog.winfo_height())
                ImageGrab.grab(bbox=dbox).save(shot_dir / "settings.png")
                dialog.destroy()
                app.plan_dialog(build_plan(app.project, app.selected_tables()))
                root.update()
                dialog = current_dialog(root)
                parent_note = dialog.code_panel.master
                parent_note.select(dialog.code_panel)
                root.update()
                dbox = (dialog.winfo_rootx(), dialog.winfo_rooty(), dialog.winfo_rootx()+dialog.winfo_width(), dialog.winfo_rooty()+dialog.winfo_height())
                ImageGrab.grab(bbox=dbox).save(shot_dir / "conversion_preview.png")
                dialog.destroy()
                app.show_home()
                root.update()
                ImageGrab.grab(bbox=box).save(shot_dir / "projects.png")
            assert not errors, errors
            root.destroy()
    print("GUI smoke: separate data/code scopes, complete 3-file preview, selection independence, exact confirmation, copy, no preview writes, retained-only preview, stale error clearing/recovery, settings, routes, actual conversion and idempotency — OK")


if __name__ == "__main__":
    main()
