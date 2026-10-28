"""Structured LLM calls with validation, repair, and a model per stage.

Every model output is a Pydantic object. The OpenAI-compatible provider asks
for JSON matching the schema, validates it, and on failure sends the
validation errors back for a bounded number of repair turns — the model fixes
its own JSON instead of the pipeline crashing or silently accepting garbage.

The router gives each stage its own model: generation and audit are
deliberately *different* models, so the auditor is a second opinion, not the
generator grading its own homework.

`OfflineAnalyst` implements the same three calls with transparent heuristics,
so the full graph runs (and is tested) without network or keys.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from processlens.schemas import (Candidate, CandidateList, CriticNote, CriticReview, Evidence, ProcessDocument,
                                 ProcessModel, QuestionAnswer, Questionnaire)
from processlens.document import fold

T = TypeVar("T", bound=BaseModel)
PROMPTS = Path(__file__).parent / "prompts"
STAGES = ("generate", "critic", "questionnaire")


class StructuredOutputError(Exception):
    pass


@dataclass
class Usage:
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    repairs: int = 0


class Provider(Protocol):
    def structured(self, *, stage: str, model: str, system: str, user: str, schema: type[T],
                   context: dict[str, Any]) -> tuple[T, Usage]: ...


def prompt(name: str) -> str:
    return (PROMPTS / f"{name}.md").read_text(encoding="utf-8")


# ---------------------------------------------------------------- OpenAI-compatible

class OpenAICompatible:
    def __init__(self, base_url: str, api_key: str, max_repairs: int = 2,
                 transport: httpx.BaseTransport | None = None) -> None:
        self.max_repairs = max_repairs
        self._http = httpx.Client(base_url=base_url, timeout=120, transport=transport,
                                  headers={"Authorization": f"Bearer {api_key}"})

    def structured(self, *, stage, model, system, user, schema, context):
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        usage = Usage(model=model)
        for attempt in range(self.max_repairs + 1):
            r = self._http.post("/chat/completions", json={
                "model": model, "messages": messages, "temperature": 0,
                "response_format": {"type": "json_schema", "json_schema": {
                    "name": schema.__name__, "schema": schema.model_json_schema()}},
            })
            r.raise_for_status()
            data = r.json()
            u = data.get("usage", {})
            usage.tokens_in += u.get("prompt_tokens", 0)
            usage.tokens_out += u.get("completion_tokens", 0)
            content = data["choices"][0]["message"]["content"] or ""
            try:
                return schema.model_validate_json(_strip_fences(content)), usage
            except ValidationError as e:
                usage.repairs = attempt + 1
                messages += [{"role": "assistant", "content": content},
                             {"role": "user", "content": "That JSON does not match the schema:\n"
                              + json.dumps(e.errors(include_url=False)[:8], default=str)
                              + "\nReturn only the corrected JSON."}]
        raise StructuredOutputError(f"{stage}: no valid {schema.__name__} after {self.max_repairs} repairs")


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    return text


# ---------------------------------------------------------------- offline analyst

# (technique, verbs that suggest it). First match wins; order encodes precedence.
_RULES: list[tuple[str, list[str], str]] = [
    ("decision_support", ["approve", "aprovar", "authorize", "autorizar"],
     "A human decision stays human; the system can pre-assemble the evidence and a recommendation."),
    ("document_ai", ["extract", "extrair", "read pdf", "ler", "fields", "campos", "ocr"],
     "Field extraction from PDFs is a solved document-AI task with confidence scores and human review."),
    ("llm_classification", ["classify", "classificar", "route", "triar", "triage", "categoriz"],
     "Classification into a small fixed set of categories suits an LLM or a small classifier."),
    ("rules_engine", ["check", "conferir", "validate", "validar", "verify", "verificar", "match"],
     "The check follows written criteria, so it can be expressed as deterministic rules."),
    ("api_integration", ["enter", "lancar", "register", "registrar", "into the", "no sistema"],
     "Re-typing data into a system of record is better replaced by an integration."),
    ("rpa", ["download", "baixar", "copy", "copiar", "preencher", "fill"],
     "Repetitive UI steps on stable screens are a fit for RPA."),
    ("notification", ["send", "enviar", "notify", "notificar", "e-mail", "email"],
     "Templated messages triggered by a state change are trivial to automate."),
]


TECHNIQUE_LABEL = {"decision_support": "Decision support", "document_ai": "Document AI",
                   "llm_classification": "LLM triage", "rules_engine": "Rules engine",
                   "api_integration": "API integration", "rpa": "RPA", "notification": "Auto-notify"}


def _stems(text: str) -> set[str]:
    return {w[:5] for w in fold(text).replace("-", " ").split() if len(w) > 3}


def _best_sentence(task_name: str, doc: ProcessDocument) -> tuple[str, str] | None:
    """The description sentence that talks most about this task (shared word stems)."""
    target = _stems(task_name)
    scored = sorted(((len(target & _stems(s.text)) / max(len(target), 1), s) for s in doc.sentences),
                    key=lambda x: -x[0])
    if scored and scored[0][0] >= 0.25:
        return scored[0][1].id, scored[0][1].text
    return None


class OfflineAnalyst:
    """Deterministic stand-in for the three model calls."""

    def structured(self, *, stage, model, system, user, schema, context):
        handler = {"generate": self._generate, "critic": self._critic, "questionnaire": self._questionnaire}[stage]
        out = handler(**context)
        return schema.model_validate(out.model_dump()), Usage(model=model, tokens_in=len(user) // 4,
                                                              tokens_out=len(out.model_dump_json()) // 4)

    def _generate(self, process: ProcessModel, doc: ProcessDocument, **_) -> CandidateList:
        candidates = []
        for task in process.tasks:
            if task.kind in ("serviceTask", "scriptTask"):
                continue   # already automated
            name = fold(task.name)
            for technique, verbs, why in _RULES:
                if any(v in name for v in verbs):
                    evidence = [Evidence(source="bpmn", ref=task.id, quote=task.name)]
                    if hit := _best_sentence(task.name, doc):
                        evidence.append(Evidence(source="doc", ref=hit[0], quote=hit[1][:160]))
                    candidates.append(Candidate(
                        id=f"C{len(candidates) + 1}", title=f"{TECHNIQUE_LABEL[technique]}: {task.name}", task_ids=[task.id],
                        technique=technique, rationale=why, evidence=evidence))
                    break
        return CandidateList(candidates=candidates)

    def _critic(self, candidates: list[Candidate], process: ProcessModel, **_) -> CriticReview:
        notes, by_technique = [], {}
        order = {t.id: i for i, t in enumerate(process.tasks)}
        for c in candidates:
            prev = by_technique.get(c.technique)
            adjacent = prev and abs(order.get(prev.task_ids[-1], -9) - order.get(c.task_ids[0], 9)) == 1
            if adjacent and c.technique in ("rpa", "api_integration"):
                notes.append(CriticNote(candidate_id=c.id, action="merge", merge_into=prev.id,
                                        reason="adjacent steps with the same technique are one automation"))
                continue
            by_technique[c.technique] = c
            notes.append(CriticNote(candidate_id=c.id, action="keep", reason="distinct, evidenced opportunity"))
        return CriticReview(notes=notes)

    def _questionnaire(self, candidate: Candidate, process: ProcessModel, doc: ProcessDocument,
                       questions: list[dict], **_) -> Questionnaire:
        """Answers from the candidate's own evidence sentence first, then from process-wide facts."""
        f, m, tech = doc.facts, doc.facts.mentions, candidate.technique
        local = next((e.ref for e in candidate.evidence if e.source == "doc"), None)
        local_signals = {sig for sig, ids in m.items() if local in ids}

        def ref(signal: str) -> str | None:
            return local if signal in local_signals else (m.get(signal) or [None])[0]

        answers: dict[str, QuestionAnswer] = {}

        def put(q: str, a: str, evidence: str | None, why: str) -> None:
            answers[q] = QuestionAnswer(question=q, answer=a if evidence else "NI", evidence_ref=evidence,
                                        justification=why if evidence else "not stated in the description")

        v = f.monthly_volume
        put("volume", "high" if v and v >= 500 else "medium" if v and v >= 100 else "low", ref("volume"),
            f"about {v} cases per month")

        # effort is process-wide; how much of it this step holds depends on what the step does
        t = f.minutes_per_case or 0
        share = {"document_ai": 0.35, "api_integration": 0.3, "rules_engine": 0.25, "llm_classification": 0.1,
                 "rpa": 0.1, "notification": 0.05, "decision_support": 0.15}[tech]
        step_minutes = t * share
        put("time_per_case", "high" if step_minutes >= 4 else "medium" if step_minutes >= 1.5 else "low", ref("time"),
            f"~{step_minutes:.1f} of {t} minutes per case sit in this step")

        rules = ref("rules")
        level = {"rules_engine": "high", "notification": "high", "api_integration": "high", "rpa": "high",
                 "llm_classification": "medium", "document_ai": "medium", "decision_support": "low"}[tech]
        put("rule_based", level if rules else "low", rules or local, "explicit criteria are documented"
            if rules else "no written criteria found")

        structured, unstructured = ref("structured") or ref("api"), ref("unstructured") or ref("paper")
        if "unstructured" in local_signals or "paper" in local_signals:
            put("digital_input", "low", local, "this step consumes PDFs, e-mails or paper")
        elif tech in ("notification", "api_integration", "rules_engine"):
            put("digital_input", "high" if structured else "medium", structured or unstructured or local,
                "works on data already captured upstream")
        else:
            put("digital_input", "medium" if unstructured else "high", unstructured or structured,
                "inputs arrive as attachments" if unstructured else "inputs are structured")

        api_ref = ref("api")
        no_api = bool(api_ref) and any(w in fold(doc.sentence(api_ref).text)
                                       for w in ("nao possui", "no api", "does not have", "without api"))
        if tech in ("api_integration", "rpa"):
            put("system_access", "low" if no_api else "high" if api_ref else "medium", api_ref or ref("manual"),
                "the system has no API (UI only)" if no_api else "an API exists" if api_ref else "UI access only")
        else:
            put("system_access", "high" if tech in ("notification", "rules_engine") else "medium",
                api_ref or ref("manual") or local, "needs only read access to data already in hand")

        exc = ref("exceptions")
        put("exception_rate", "high" if exc and exc == local else "medium" if exc else "low", exc or local,
            "rework is reported for this step" if exc == local else "rework is reported for the process"
            if exc else "no rework reported")
        put("stability", "high" if ref("stable") else "low" if ref("changing") else "medium",
            ref("stable") or ref("changing"), "rules are reported stable" if ref("stable") else "rules change")
        comp = ref("compliance")
        put("compliance_risk", "high" if comp and tech in ("decision_support", "rules_engine") else
            "medium" if comp else "low", comp or local, "the activity is audited" if comp else "no audit signal")
        return Questionnaire(candidate_id=candidate.id,
                             answers=[answers[q["id"]] for q in questions if q["id"] in answers])


# ---------------------------------------------------------------- router

@dataclass
class Router:
    provider: Provider
    models: dict[str, str] = field(default_factory=dict)
    usage: list[Usage] = field(default_factory=list)

    def call(self, stage: str, system: str, user: str, schema: type[T], context: dict[str, Any]) -> T:
        model = self.models.get(stage, "offline/analyst-v1")
        started = time.perf_counter()
        out, usage = self.provider.structured(stage=stage, model=model, system=system, user=user, schema=schema,
                                              context=context)
        usage.tokens_in = usage.tokens_in or 0
        self.usage.append(usage)
        _ = time.perf_counter() - started
        return out


def from_env() -> Router:
    """`PL_PROVIDER=openai` + `LLM_API_KEY` (from your environment) for a real model; offline otherwise."""
    models = {s: os.environ.get(f"PL_MODEL_{s.upper()}", "offline/analyst-v1") for s in STAGES}
    if os.environ.get("PL_PROVIDER") == "openai":
        key = os.environ.get("LLM_API_KEY")
        if not key:
            raise RuntimeError("PL_PROVIDER=openai needs LLM_API_KEY in the environment")
        return Router(OpenAICompatible(os.environ.get("LLM_BASE_URL", "https://openrouter.ai/api/v1"), key), models)
    return Router(OfflineAnalyst(), models)
