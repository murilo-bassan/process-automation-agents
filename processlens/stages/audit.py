"""Independent auditor: flags, never edits.

Generation and audit are separate on purpose. The auditor reads the final
candidates and their scores and raises issues; it does not rewrite or remove
anything — that keeps "what the system proposed" and "what the reviewer
should look at" distinguishable in the report.
"""
from __future__ import annotations

from processlens.document import fold
from processlens.schemas import Candidate, Issue, ProcessModel, Score


def audit(candidates: list[Candidate], scores: list[Score], process: ProcessModel) -> list[Issue]:
    issues: list[Issue] = []
    by_id = {s.candidate_id: s for s in scores}
    for c in candidates:
        names = " ".join(fold(process.task(t).name) for t in c.task_ids if process.task(t))
        s = by_id.get(c.id)
        if any(w in names for w in ("approve", "aprovar", "authorize", "autorizar")) and c.technique != "decision_support":
            issues.append(Issue(stage="audit", severity="blocker", candidate_id=c.id,
                                message="automates a human approval; only decision support is acceptable"))
        if s and s.coverage < 0.5:
            issues.append(Issue(stage="audit", severity="warning", candidate_id=c.id,
                                message=f"only {s.coverage:.0%} of the questionnaire is evidenced; collect data before committing"))
        if c.technique in ("llm_classification", "document_ai"):
            risk = next((a.answer for a in (s.answers if s else []) if a.question == "compliance_risk"), "NI")
            if risk in ("high", "medium"):
                issues.append(Issue(stage="audit", severity="warning", candidate_id=c.id,
                                    message="probabilistic step in an audited flow: keep human review on low-confidence cases"))
        if c.technique == "rpa":
            issues.append(Issue(stage="audit", severity="info", candidate_id=c.id,
                                message="RPA breaks when screens change; prefer an API if one appears"))
    if len(candidates) == 0:
        issues.append(Issue(stage="audit", severity="info", message="no candidate survived traceability"))
    return issues
