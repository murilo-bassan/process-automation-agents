"""Traceability guard: no claim survives without evidence that actually exists.

For every candidate:
  * each `task_id` must be a task in the BPMN;
  * each evidence `ref` must exist (a BPMN element or a sentence id);
  * each `quote` must really appear in what it references (accent/case-folded,
    with a small fuzzy allowance for whitespace and punctuation);
  * at least one valid BPMN evidence AND one valid description evidence must remain.

Invalid evidence is removed and reported; a candidate left without both kinds is
dropped. This is where model hallucinations stop — mechanically, before scoring.
"""
from __future__ import annotations

import difflib
import re

from processlens.document import fold
from processlens.schemas import Candidate, Evidence, Issue, ProcessDocument, ProcessModel


def quote_found(quote: str, haystack: str, threshold: float = 0.9) -> bool:
    q = " ".join(re.sub(r"[^a-z0-9 ]+", " ", fold(quote)).split())
    h = " ".join(re.sub(r"[^a-z0-9 ]+", " ", fold(haystack)).split())
    if not q:
        return False
    if q in h:
        return True
    window = len(q)
    best = max((difflib.SequenceMatcher(None, q, h[i:i + window]).ratio()
                for i in range(0, max(1, len(h) - window + 1), max(1, window // 4))), default=0.0)
    return best >= threshold


def _evidence_ok(e: Evidence, process: ProcessModel, doc: ProcessDocument) -> str | None:
    if e.source == "bpmn":
        el = process.task(e.ref) or next((g for g in process.gateways if g.id == e.ref), None)
        if el is None:
            return f"BPMN element '{e.ref}' does not exist"
        if not quote_found(e.quote, el.name or ""):
            return f"quote not found in BPMN element '{e.ref}'"
        return None
    s = doc.sentence(e.ref)
    if s is None:
        return f"sentence '{e.ref}' does not exist"
    if not quote_found(e.quote, s.text):
        return f"quote not found in {e.ref}"
    return None


def verify(candidates: list[Candidate], process: ProcessModel, doc: ProcessDocument) -> tuple[list[Candidate], list[Issue]]:
    kept, issues = [], []
    for c in candidates:
        unknown = [t for t in c.task_ids if process.task(t) is None]
        if unknown:
            issues.append(Issue(stage="trace", severity="blocker", candidate_id=c.id,
                                message=f"dropped: references tasks that do not exist {unknown}"))
            continue
        valid = []
        for e in c.evidence:
            problem = _evidence_ok(e, process, doc)
            if problem:
                issues.append(Issue(stage="trace", severity="warning", candidate_id=c.id, message=f"evidence removed: {problem}"))
            else:
                valid.append(e)
        sources = {e.source for e in valid}
        if sources != {"bpmn", "doc"}:
            missing = {"bpmn", "doc"} - sources
            issues.append(Issue(stage="trace", severity="blocker", candidate_id=c.id,
                                message=f"dropped: no valid evidence from {', '.join(sorted(missing))}"))
            continue
        kept.append(c.model_copy(update={"evidence": valid}))
    return kept, issues
