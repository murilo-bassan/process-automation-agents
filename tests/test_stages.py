from processlens.schemas import Candidate, Evidence, QuestionAnswer, Questionnaire
from processlens.stages import audit, score, trace


def cand(cid="C1", tasks=("t_check_po",), technique="rules_engine", evidence=None):
    return Candidate(id=cid, title="x", task_ids=list(tasks), technique=technique, rationale="r",
                     evidence=evidence or [Evidence(source="bpmn", ref="t_check_po", quote="Check invoice against purchase order"),
                                           Evidence(source="doc", ref="S9", quote="fixed checklist with a 2% price tolerance")])


def test_trace_keeps_valid(process, doc):
    kept, issues = trace.verify([cand()], process, doc)
    assert len(kept) == 1 and issues == []


def test_trace_drops_hallucinated_task(process, doc):
    kept, issues = trace.verify([cand(tasks=("t_ghost",))], process, doc)
    assert kept == [] and "do not exist" in issues[0].message


def test_trace_drops_when_quote_is_invented(process, doc):
    fake = [Evidence(source="bpmn", ref="t_check_po", quote="Check invoice against purchase order"),
            Evidence(source="doc", ref="S9", quote="the CFO personally signs every invoice")]
    kept, issues = trace.verify([cand(evidence=fake)], process, doc)
    assert kept == []
    assert [i.severity for i in issues] == ["warning", "blocker"]
    assert "quote not found in S9" in issues[0].message


def test_trace_drops_nonexistent_sentence(process, doc):
    fake = [Evidence(source="bpmn", ref="t_check_po", quote="Check invoice"), Evidence(source="doc", ref="S999", quote="anything")]
    kept, issues = trace.verify([cand(evidence=fake)], process, doc)
    assert kept == [] and "S999" in issues[0].message


def test_quote_tolerates_case_accents_punctuation():
    assert trace.quote_found("Política de viagens!", "o analista confere contra a politica de viagens, que define")
    assert not trace.quote_found("budget is unlimited", "the budget owner approves exceptions")


def _q(cid, **answers):
    return Questionnaire(candidate_id=cid, answers=[QuestionAnswer(question=k, answer=v, evidence_ref=None if v == "NI" else "S1")
                                                    for k, v in answers.items()])


def test_score_is_deterministic_and_bounded():
    full = {q["id"]: "high" for q in score.QUESTIONS}
    a, b = score.score(cand(), _q("C1", **full)), score.score(cand(), _q("C1", **full))
    assert a == b
    assert 0 <= a.impact <= 1 and 0 <= a.feasibility <= 1 and a.coverage == 1


def test_ni_lowers_coverage_and_score():
    full = {q["id"]: "high" for q in score.QUESTIONS}
    partial = {**full, "volume": "NI", "rule_based": "NI"}
    s_full, s_partial = score.score(cand(), _q("C1", **full)), score.score(cand(), _q("C1", **partial))
    assert s_partial.coverage == 0.75
    assert s_partial.impact < s_full.impact and s_partial.feasibility < s_full.feasibility


def test_answer_without_evidence_counts_as_ni():
    q = Questionnaire(candidate_id="C1", answers=[QuestionAnswer(question="volume", answer="high", evidence_ref=None)])
    assert score.score(cand(), q).breakdown["volume"] == 0


def test_document_ai_not_punished_for_unstructured_input():
    answers = {q["id"]: "high" for q in score.QUESTIONS} | {"digital_input": "low"}
    plain = score.score(cand(technique="rpa"), _q("C1", **answers))
    docai = score.score(cand(technique="document_ai"), _q("C1", **answers))
    assert docai.feasibility > plain.feasibility


def test_audit_blocks_automated_approvals(process):
    approval = cand(tasks=("t_approve",), technique="rules_engine")
    issues = audit.audit([approval], [], process)
    assert any(i.severity == "blocker" and "human approval" in i.message for i in issues)
    ok = audit.audit([cand(tasks=("t_approve",), technique="decision_support")], [], process)
    assert not any(i.severity == "blocker" for i in ok)
