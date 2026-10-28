"""Data contracts between pipeline stages.

Every claim a model makes about the process carries `Evidence` that points at
something that exists: a BPMN element id or a sentence id of the description.
The trace stage verifies those pointers mechanically before anything is scored.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

TaskKind = Literal["userTask", "manualTask", "serviceTask", "scriptTask", "sendTask", "receiveTask",
                   "businessRuleTask", "task"]
Technique = Literal["rules_engine", "rpa", "api_integration", "document_ai", "llm_classification",
                    "notification", "decision_support"]


# ---------------------------------------------------------------- inputs

class Task(BaseModel):
    id: str
    name: str
    kind: TaskKind
    lane: str | None = None


class Flow(BaseModel):
    id: str
    source: str
    target: str
    name: str | None = None


class Gateway(BaseModel):
    id: str
    name: str | None = None
    kind: str


class ProcessModel(BaseModel):
    id: str
    name: str
    tasks: list[Task]
    gateways: list[Gateway]
    flows: list[Flow]
    lanes: list[str]

    def task(self, task_id: str) -> Task | None:
        return next((t for t in self.tasks if t.id == task_id), None)

    @property
    def manual_tasks(self) -> list[Task]:
        return [t for t in self.tasks if t.kind in ("userTask", "manualTask", "task")]

    @property
    def handoffs(self) -> int:
        """Flows that cross from one lane to another — where work waits in someone's inbox."""
        lane_of = {t.id: t.lane for t in self.tasks}
        return sum(1 for f in self.flows if lane_of.get(f.source) and lane_of.get(f.target)
                   and lane_of[f.source] != lane_of[f.target])


class Sentence(BaseModel):
    id: str          # "S12"
    section: str
    text: str


class DocumentFacts(BaseModel):
    monthly_volume: int | None = None
    minutes_per_case: int | None = None
    systems: list[str] = Field(default_factory=list)
    mentions: dict[str, list[str]] = Field(default_factory=dict)   # signal -> sentence ids


class ProcessDocument(BaseModel):
    title: str
    sentences: list[Sentence]
    facts: DocumentFacts

    def sentence(self, sid: str) -> Sentence | None:
        return next((s for s in self.sentences if s.id == sid), None)


# ---------------------------------------------------------------- model outputs

class Evidence(BaseModel):
    source: Literal["bpmn", "doc"]
    ref: str                         # BPMN element id or sentence id
    quote: str = Field(min_length=2)  # must actually appear in the referenced element


class Candidate(BaseModel):
    id: str
    title: str
    task_ids: list[str] = Field(min_length=1)
    technique: Technique
    rationale: str
    evidence: list[Evidence] = Field(min_length=1)


class CandidateList(BaseModel):
    candidates: list[Candidate]


class CriticNote(BaseModel):
    candidate_id: str
    action: Literal["keep", "merge", "drop"]
    merge_into: str | None = None
    reason: str


class CriticReview(BaseModel):
    notes: list[CriticNote]


Answer = Literal["high", "medium", "low", "NI"]


class QuestionAnswer(BaseModel):
    question: str
    answer: Answer
    evidence_ref: str | None = None     # sentence id; required unless NI
    justification: str = ""


class Questionnaire(BaseModel):
    candidate_id: str
    answers: list[QuestionAnswer]


# ---------------------------------------------------------------- outputs

class Issue(BaseModel):
    stage: str
    severity: Literal["blocker", "warning", "info"]
    candidate_id: str | None = None
    message: str


class Score(BaseModel):
    candidate_id: str
    impact: float            # 0..1
    feasibility: float       # 0..1
    coverage: float          # share of questions answered with evidence (not NI)
    quadrant: Literal["quick_win", "strategic", "fill_in", "reconsider"]
    breakdown: dict[str, float]
    answers: list[QuestionAnswer]


class StageTiming(BaseModel):
    stage: str
    ms: int
    model: str | None = None
