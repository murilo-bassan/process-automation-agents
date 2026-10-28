import json

import httpx
import pytest
from fastapi.testclient import TestClient

from processlens import graph, llm, report
from processlens.api import app
from processlens.schemas import Candidate, CandidateList, Evidence, Questionnaire
from tests.conftest import SAMPLES, make_pdf


def run(router=None, name="invoice-intake"):
    return graph.analyze(router or llm.Router(llm.OfflineAnalyst()), (SAMPLES / f"{name}.bpmn").read_bytes(),
                         f"{name}.md", (SAMPLES / f"{name}.md").read_bytes())


def test_graph_end_to_end():
    s = run()
    assert [t.stage for t in s["timings"]][-5:] == ["critic", "trace", "questionnaire", "score", "audit"]
    assert {t.stage for t in s["timings"][:2]} == {"parse_bpmn", "read_doc"}       # parallel branches
    ids = {c.task_ids[0] for c in s["candidates"]}
    assert "t_schedule" not in ids                                                     # serviceTask: already automated
    approval = next(c for c in s["candidates"] if "t_approve" in c.task_ids)
    assert approval.technique == "decision_support"
    assert all(sc.coverage > 0.5 for sc in s["scores"])
    best = max(s["scores"], key=lambda x: x.impact + x.feasibility)
    assert best.quadrant == "quick_win"


def test_offline_pipeline_is_reproducible():
    a, b = report.to_dict(run()), report.to_dict(run())
    strip = lambda d: {k: v for k, v in d.items() if k != "timings"}  # noqa: E731
    assert strip(a) == strip(b)


class Hallucinating(llm.OfflineAnalyst):
    """Adds one invented candidate and cites a sentence that does not exist."""

    def structured(self, *, stage, model, system, user, schema, context):
        out, usage = super().structured(stage=stage, model=model, system=system, user=user, schema=schema, context=context)
        if stage == "generate":
            out.candidates.append(Candidate(id="C99", title="Blockchain: everything", task_ids=["t_receive"],
                                            technique="rpa", rationale="trust me",
                                            evidence=[Evidence(source="bpmn", ref="t_receive", quote="Download invoice"),
                                                      Evidence(source="doc", ref="S2", quote="the board mandated blockchain")]))
        if stage == "questionnaire":
            out.answers[0].evidence_ref = "S404"
        return out, usage


def test_hallucinations_are_stopped():
    s = run(llm.Router(Hallucinating()))
    assert "C99" not in {c.id for c in s["candidates"]}
    messages = [i.message for i in s["issues"]]
    assert any("quote not found in S2" in m for m in messages)
    assert any("S404, which does not exist" in m for m in messages)
    assert all(q.answers[0].answer == "NI" for q in s["questionnaires"])


def test_critic_merges_adjacent_same_technique():
    class Twin(llm.OfflineAnalyst):
        def _generate(self, process, doc, **_):
            out = super()._generate(process, doc)
            for c in out.candidates:
                if c.task_ids == ["t_extract"]:
                    c.technique = "api_integration"
                if c.task_ids == ["t_check_po"]:
                    c.technique = "api_integration"
            return out

    s = run(llm.Router(Twin()))
    merged = [c for c in s["candidates"] if c.task_ids == ["t_extract", "t_check_po"]]
    assert merged and any("merged into" in i.message for i in s["issues"])


def test_openai_provider_repairs_invalid_json():
    replies = iter(['{"candidates": [{"id": "C1"}]}',                      # missing fields
                    '```json\n{"candidates": []}\n```'])                    # valid, fenced
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": next(replies)}}],
                                         "usage": {"prompt_tokens": 10, "completion_tokens": 5}})

    provider = llm.OpenAICompatible("https://llm.example", "test-key", transport=httpx.MockTransport(handler))
    out, usage = provider.structured(stage="generate", model="m", system="s", user="u", schema=CandidateList, context={})
    assert out.candidates == [] and usage.repairs == 1 and usage.tokens_in == 20
    assert "does not match the schema" in seen[1]["messages"][-1]["content"]
    assert seen[0]["response_format"]["json_schema"]["name"] == "CandidateList"


def test_openai_provider_gives_up():
    handler = lambda r: httpx.Response(200, json={"choices": [{"message": {"content": "not json"}}]})  # noqa: E731
    provider = llm.OpenAICompatible("https://x", "k", max_repairs=1, transport=httpx.MockTransport(handler))
    with pytest.raises(llm.StructuredOutputError):
        provider.structured(stage="critic", model="m", system="s", user="u", schema=Questionnaire, context={})


def test_reports_render():
    data = report.to_dict(run(name="reembolso-viagem"))
    md, html, docx = report.to_markdown(data), report.to_html(data), report.to_docx(data)
    assert "| C" in md and "Reembolso" in md
    assert "<script" not in html and "priority matrix" in html
    assert docx[:2] == b"PK"   # a zip container


def test_api_sample_and_downloads():
    c = TestClient(app)
    r = c.post("/v1/samples/invoice-intake").json()
    assert r["candidates"] and r["process"]["tasks"] == 8
    assert c.get(f"/v1/analyses/{r['id']}/report.docx").headers["content-type"].startswith("application/vnd.openxml")
    assert c.get(f"/v1/analyses/{r['id']}/report.md").text.startswith("# Automation assessment")
    assert c.post("/v1/samples/nope").status_code == 404


def test_api_upload_with_pdf_description():
    c = TestClient(app)
    pdf = make_pdf(["Expense claims", "Analysts check each receipt against the travel policy rules.",
                    "We receive about 300 claims per month and each takes 20 minutes."])
    r = c.post("/v1/analyses", files={"bpmn_file": ("p.bpmn", (SAMPLES / "reembolso-viagem.bpmn").read_bytes()),
                                      "description": ("d.pdf", pdf, "application/pdf")})
    assert r.status_code == 200 and r.json()["document"]["facts"]["monthly_volume"] == 300


def test_api_rejects_bad_bpmn():
    c = TestClient(app)
    r = c.post("/v1/analyses", files={"bpmn_file": ("x.bpmn", b"<nope"), "description": ("d.md", b"# x\nSome text here.")})
    assert r.status_code == 422 and r.json()["detail"]["error"] == "invalid_bpmn"
