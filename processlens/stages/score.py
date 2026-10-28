"""Deterministic scoring: the model answers questions, the rubric computes the number.

Letting a model output "priority: 8.5/10" makes the number unexplainable and
unstable between runs. Here the model (or the offline analyst) only answers a
fixed questionnaire with cited evidence; this module turns answers into impact
and feasibility with published weights. Same answers → same score, always.
"""
from __future__ import annotations

from processlens.schemas import Candidate, Questionnaire, Score

# id, axis, weight, text, and how each answer maps to points (NI is always 0).
QUESTIONS = [
    {"id": "volume", "axis": "impact", "weight": 0.35, "text": "How many cases per month?",
     "points": {"high": 1.0, "medium": 0.6, "low": 0.2}},
    {"id": "time_per_case", "axis": "impact", "weight": 0.35, "text": "How much effort per case?",
     "points": {"high": 1.0, "medium": 0.6, "low": 0.2}},
    {"id": "compliance_risk", "axis": "impact", "weight": 0.30,
     "text": "Would errors here create compliance risk (that automation would reduce)?",
     "points": {"high": 0.8, "medium": 0.6, "low": 0.3}},
    {"id": "rule_based", "axis": "feasibility", "weight": 0.25, "text": "Is the work driven by explicit rules?",
     "points": {"high": 1.0, "medium": 0.5, "low": 0.1}},
    {"id": "digital_input", "axis": "feasibility", "weight": 0.20, "text": "Are inputs digital and structured?",
     "points": {"high": 1.0, "medium": 0.6, "low": 0.1}},
    {"id": "system_access", "axis": "feasibility", "weight": 0.20, "text": "Can the systems be reached by API?",
     "points": {"high": 1.0, "medium": 0.6, "low": 0.3}},
    {"id": "exception_rate", "axis": "feasibility", "weight": 0.15, "text": "How often do cases fall out of the happy path?",
     "points": {"high": 0.1, "medium": 0.5, "low": 1.0}},
    {"id": "stability", "axis": "feasibility", "weight": 0.20, "text": "Are the process and its rules stable?",
     "points": {"high": 1.0, "medium": 0.6, "low": 0.1}},
]

# Technique-specific feasibility adjustment: what the technique tolerates.
TECHNIQUE_TOLERANCE = {"document_ai": {"digital_input": 0.4}, "llm_classification": {"rule_based": 0.3},
                       "decision_support": {}}

THRESHOLD = 0.55


def score(candidate: Candidate, q: Questionnaire) -> Score:
    answers = {a.question: a for a in q.answers}
    axes = {"impact": 0.0, "feasibility": 0.0}
    breakdown: dict[str, float] = {}
    answered = 0
    tolerance = TECHNIQUE_TOLERANCE.get(candidate.technique, {})
    for question in QUESTIONS:
        a = answers.get(question["id"])
        if a is None or a.answer == "NI" or not a.evidence_ref:
            pts = 0.0
        else:
            answered += 1
            pts = question["points"][a.answer]
            # document AI exists *because* inputs are unstructured: don't punish it for that
            pts = max(pts, tolerance.get(question["id"], 0.0))
        contribution = round(pts * question["weight"], 4)
        breakdown[question["id"]] = contribution
        axes[question["axis"]] += contribution
    impact, feasibility = round(axes["impact"], 3), round(axes["feasibility"], 3)
    quadrant = ("quick_win" if impact >= THRESHOLD and feasibility >= THRESHOLD else
                "strategic" if impact >= THRESHOLD else
                "fill_in" if feasibility >= THRESHOLD else "reconsider")
    return Score(candidate_id=candidate.id, impact=impact, feasibility=feasibility,
                 coverage=round(answered / len(QUESTIONS), 3), quadrant=quadrant, breakdown=breakdown,
                 answers=list(q.answers))
