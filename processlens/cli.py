"""Command line: analyze a BPMN + description and write every report format.

    python -m processlens.cli samples/invoice-intake.bpmn samples/invoice-intake.md --out out/
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from processlens import graph, llm, report


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("bpmn", type=Path)
    ap.add_argument("description", type=Path, help=".md, .txt or .pdf")
    ap.add_argument("--out", type=Path, default=Path("out"))
    args = ap.parse_args()

    state = graph.analyze(llm.from_env(), args.bpmn.read_bytes(), args.description.name, args.description.read_bytes())
    data = report.to_dict(state)
    args.out.mkdir(parents=True, exist_ok=True)
    stem = args.bpmn.stem
    (args.out / f"{stem}.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    (args.out / f"{stem}.md").write_text(report.to_markdown(data), encoding="utf-8")
    (args.out / f"{stem}.html").write_text(report.to_html(data), encoding="utf-8")
    (args.out / f"{stem}.docx").write_bytes(report.to_docx(data))
    print(f"{len(data['candidates'])} candidates · {len(data['issues'])} review notes → {args.out}/{stem}.(json|md|html|docx)")


if __name__ == "__main__":
    main()
