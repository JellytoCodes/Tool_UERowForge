"""UERowForge entry point. Python 3.10+; zero pip dependencies."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="UERowForge — Excel to Unreal DataTable prototype")
    parser.add_argument("--demo", action="store_true", help="Open the safe, conversion-only demo project")
    parser.add_argument("--validate", nargs="+", metavar="XLSX", help="Validate Excel files without GUI or project writes")
    args = parser.parse_args()
    if sys.version_info < (3, 10):
        parser.error("Python 3.10 이상이 필요합니다.")
    if args.validate:
        from uerowforge.core import load_tables
        tables, issues = load_tables([Path(p) for p in args.validate])
        issues += [i for t in tables for i in t.issues]
        payload = {"ok": not issues and bool(tables),
                   "tables": [{"name": t.name, "rows": len(t.rows), "valid": t.valid, "schema": t.schema()} for t in tables],
                   "issues": list(map(str, issues))}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if payload["ok"] else 1
    from uerowforge.gui import launch
    launch(demo=args.demo)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
