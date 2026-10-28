"""The analysis pipeline as a LangGraph state machine.

        ┌─ parse_bpmn ──┐
  START ┤               ├─► generate ─► critic ─► trace ─► questionnaire ─► score ─► audit ─► END
        └─ read_doc ────┘      (LLM)     (LLM)    (rules)      (LLM)        (rules)  (rules)

Nodes are thin: each calls one domain function and returns a partial state.
`issues` and `timings` use additive reducers, so every node appends without
knowing about the others. Model calls go through the `Router` (one model per
stage); everything that decides — what survives, what it scores — is code.
"""
from __future__ import annotations

import json
import operator
import time
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

from processlens import bpmn, document
from processlens.llm import Router, prompt
from processlens.schemas import (Candidate, CandidateList, CriticReview, Issue, ProcessDocument, ProcessModel,
                                 Questionnaire, Score, StageTiming)
from processlens.stages import audit as audit_stage
from processlens.stages import score as score_stage
from processlens.stages import trace as trace_stage


class State(TypedDict, total=False):
    bpmn_xml: bytes
    doc_name: str
    doc_bytes: bytes
    process: ProcessModel
    doc: ProcessDocument
    proposed: list[Candidate]
    candidates: list[Candidate]
    questionnaires: list[Questionnaire]
    scores: list[Score]
    issues: Annotated[list[Issue], operator.add]
    timings: Annotated[list[StageTiming], operator.add]


def _timed(stage: str, model: str | None = None):
    def wrap(fn):
        def node(state: State) -> dict[str, Any]:
            started = time.perf_counter()
            out = fn(state)
            out.setdefault("timings", []).append(
                StageTiming(stage=stage, ms=int((time.perf_counter() - started) * 1000), model=model))
            return out
        node.__name__ = stage
        return node
    return wrap


def _process_payload(p: ProcessModel) -> str:
    return json.dumps({"process": p.name, "lanes": p.lanes,
                       "tasks": [t.model_dump() for t in p.tasks],
                       "flows": [f"{f.source}->{f.target}" + (f" [{f.name}]" if f.name else "") for f in p.flows]},
                      ensure_ascii=False)


def _doc_payload(d: ProcessDocument) -> str:
    return "\n".join(f"{s.id} ({s.section}): {s.text}" for s in d.sentences)


def build(router: Router):
    @_timed("parse_bpmn")
    def parse_bpmn(state: State) -> dict[str, Any]:
        return {"process": bpmn.parse(state["bpmn_xml"])}

    @_timed("read_doc")
    def read_doc(state: State) -> dict[str, Any]:
        return {"doc": document.load(state.get("doc_name", "description.md"), state["doc_bytes"])}

    @_timed("generate", router.models.get("generate"))
    def generate(state: State) -> dict[str, Any]:
        p, d = state["process"], state["doc"]
        out = router.call("generate", prompt("generate"),
                          f"BPMN:\n{_process_payload(p)}\n\nDESCRIPTION:\n{_doc_payload(d)}",
                          CandidateList, {"process": p, "doc": d})
        return {"proposed": out.candidates}

    @_timed("critic", router.models.get("critic"))
    def critic(state: State) -> dict[str, Any]:
        proposed = state["proposed"]
        review = router.call("critic", prompt("critic"),
                             json.dumps([c.model_dump() for c in proposed], ensure_ascii=False),
                             CriticReview, {"candidates": proposed, "process": state["process"]})
        notes = {n.candidate_id: n for n in review.notes}
        by_id = {c.id: c for c in proposed}
        kept: dict[str, Candidate] = {}
        issues = []
        for c in proposed:
            note = notes.get(c.id)
            if note and note.action == "drop":
                issues.append(Issue(stage="critic", severity="info", candidate_id=c.id, message=f"dropped: {note.reason}"))
            elif note and note.action == "merge" and note.merge_into in kept:
                target = kept[note.merge_into]
                kept[target.id] = target.model_copy(update={
                    "task_ids": target.task_ids + c.task_ids, "evidence": target.evidence + c.evidence,
                    "title": f"{target.title} + {by_id[c.id].title.split(': ', 1)[-1]}"})
                issues.append(Issue(stage="critic", severity="info", candidate_id=c.id,
                                    message=f"merged into {note.merge_into}: {note.reason}"))
            else:
                kept[c.id] = c
        return {"candidates": list(kept.values()), "issues": issues}

    @_timed("trace")
    def trace(state: State) -> dict[str, Any]:
        kept, issues = trace_stage.verify(state["candidates"], state["process"], state["doc"])
        return {"candidates": kept, "issues": issues}

    @_timed("questionnaire", router.models.get("questionnaire"))
    def questionnaire(state: State) -> dict[str, Any]:
        qs, issues = [], []
        questions = [{"id": q["id"], "text": q["text"]} for q in score_stage.QUESTIONS]
        for c in state["candidates"]:
            q = router.call("questionnaire", prompt("questionnaire"),
                            f"QUESTIONS:\n{json.dumps(questions)}\n\nCANDIDATE:\n{c.model_dump_json()}\n\n"
                            f"DESCRIPTION:\n{_doc_payload(state['doc'])}",
                            Questionnaire, {"candidate": c, "process": state["process"], "doc": state["doc"],
                                            "questions": questions})
            # an answer citing a sentence that does not exist is downgraded to NI, not trusted
            for a in q.answers:
                if a.evidence_ref and state["doc"].sentence(a.evidence_ref) is None:
                    issues.append(Issue(stage="questionnaire", severity="warning", candidate_id=c.id,
                                        message=f"{a.question}: cited {a.evidence_ref}, which does not exist → NI"))
                    a.answer, a.evidence_ref = "NI", None
            qs.append(q)
        return {"questionnaires": qs, "issues": issues}

    @_timed("score")
    def score(state: State) -> dict[str, Any]:
        by_id = {q.candidate_id: q for q in state["questionnaires"]}
        scores = [score_stage.score(c, by_id[c.id]) for c in state["candidates"] if c.id in by_id]
        return {"scores": scores}

    @_timed("audit")
    def audit(state: State) -> dict[str, Any]:
        return {"issues": audit_stage.audit(state["candidates"], state["scores"], state["process"])}

    g = StateGraph(State)
    for name, fn in [("parse_bpmn", parse_bpmn), ("read_doc", read_doc), ("generate", generate), ("critic", critic),
                     ("trace", trace), ("questionnaire", questionnaire), ("score", score), ("audit", audit)]:
        g.add_node(name, fn)
    g.add_edge(START, "parse_bpmn")
    g.add_edge(START, "read_doc")
    g.add_edge(["parse_bpmn", "read_doc"], "generate")
    for a, b in [("generate", "critic"), ("critic", "trace"), ("trace", "questionnaire"),
                 ("questionnaire", "score"), ("score", "audit"), ("audit", END)]:
        g.add_edge(a, b)
    return g.compile()


def analyze(router: Router, bpmn_xml: bytes, doc_name: str, doc_bytes: bytes) -> State:
    graph = build(router)
    return graph.invoke({"bpmn_xml": bpmn_xml, "doc_name": doc_name, "doc_bytes": doc_bytes,
                         "issues": [], "timings": []})
