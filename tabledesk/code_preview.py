"""Whole-file, read-only previews. Table selection never enters project scope."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import PurePosixPath

from .core import Plan, Project, Table, _build_plan, header_blocks


@dataclass(frozen=True)
class CodeDocument:
    relative_path: str
    text: str

    @property
    def filename(self) -> str:
        return PurePosixPath(self.relative_path).name


@dataclass(frozen=True)
class CodePreview:
    documents: tuple[CodeDocument, ...]
    included_tables: tuple[str, ...]
    incoming_tables: tuple[str, ...]
    retained_tables: tuple[str, ...]
    excluded_tables: tuple[str, ...] = ()


def code_preview_from_plan(plan: Plan) -> CodePreview:
    """Expose the exact three planned files, including pre-existing tables.

    This is also used by the conversion confirmation dialog: unlike the project
    workspace, that dialog's plan contains only the selected incoming tables.
    Do not reconstruct or concatenate per-table snippets here.
    """
    documents = tuple(CodeDocument(w.path.relative_to(plan.project.root).as_posix(),
                                   w.content.decode("utf-8-sig"))
                      for w in plan.writes if w.label.startswith("C++"))
    row_header = next(w for w in plan.writes if w.label == "C++ 헤더")
    names = tuple(sorted(header_blocks(row_header.content.decode("utf-8-sig"))))
    incoming = tuple(sorted(t.name for t in plan.tables))
    retained = tuple(n for n in names if n not in incoming)
    # A fresh project with no imported tables has no output to preview yet.
    return CodePreview(documents if names else (), names, incoming, retained)


def build_project_code_preview(project: Project, tables: list[Table]) -> CodePreview:
    """All valid imported schemas + every retained schema; never writes files.

    Invalid incoming tables are excluded explicitly. If such a table already
    exists in the project, its last generated schema remains in the preview.
    Paths, external edits, stale workbook hashes and conflicts receive exactly
    the same validation as conversion. Return display data, not an executable
    conversion Plan.
    """
    valid = [t for t in tables if t.valid]
    preview = code_preview_from_plan(_build_plan(project, valid))
    return CodePreview(preview.documents, preview.included_tables,
                       preview.incoming_tables, preview.retained_tables,
                       tuple(sorted({t.name for t in tables if not t.valid})))
