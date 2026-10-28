"""HTTP service: upload a BPMN + description, get the assessment in four formats.

    uvicorn processlens.api:app --port 8800
"""
from __future__ import annotations

import uuid
from collections import OrderedDict
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

from processlens import bpmn, graph, llm, report

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"
STATIC = ROOT / "web" / "static"
MAX_UPLOAD = 5_000_000

app = FastAPI(title="processlens", version="0.1.0", docs_url="/docs")
_store: OrderedDict[str, dict[str, Any]] = OrderedDict()   # small in-memory LRU; reports are cheap to recompute


def _remember(data: dict[str, Any]) -> dict[str, Any]:
    analysis_id = uuid.uuid4().hex[:12]
    data = {"id": analysis_id, **data}
    _store[analysis_id] = data
    while len(_store) > 50:
        _store.popitem(last=False)
    return data


def _run(bpmn_bytes: bytes, doc_name: str, doc_bytes: bytes) -> dict[str, Any]:
    try:
        state = graph.analyze(llm.from_env(), bpmn_bytes, doc_name, doc_bytes)
    except bpmn.BpmnError as e:
        raise HTTPException(422, {"error": "invalid_bpmn", "message": str(e)})
    except ValueError as e:
        raise HTTPException(422, {"error": "invalid_document", "message": str(e)})
    return _remember(report.to_dict(state))


async def _read(upload: UploadFile) -> bytes:
    data = await upload.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, f"{upload.filename} is larger than {MAX_UPLOAD // 1_000_000} MB")
    return data


@app.post("/v1/analyses")
async def analyze(bpmn_file: UploadFile = File(...), description: UploadFile = File(...)) -> dict[str, Any]:
    return _run(await _read(bpmn_file), description.filename or "description.md", await _read(description))


@app.get("/v1/samples")
def samples() -> list[str]:
    return sorted(p.stem for p in SAMPLES.glob("*.bpmn"))


@app.post("/v1/samples/{name}")
def analyze_sample(name: str) -> dict[str, Any]:
    if name not in samples():
        raise HTTPException(404, "unknown sample")
    return _run((SAMPLES / f"{name}.bpmn").read_bytes(), f"{name}.md", (SAMPLES / f"{name}.md").read_bytes())


def _get(analysis_id: str) -> dict[str, Any]:
    if analysis_id not in _store:
        raise HTTPException(404, "analysis not found (they are kept in memory)")
    return _store[analysis_id]


@app.get("/v1/analyses/{analysis_id}")
def get_json(analysis_id: str) -> dict[str, Any]:
    return _get(analysis_id)


@app.get("/v1/analyses/{analysis_id}/report.md", response_class=PlainTextResponse)
def get_md(analysis_id: str) -> str:
    return report.to_markdown(_get(analysis_id))


@app.get("/v1/analyses/{analysis_id}/report.html", response_class=HTMLResponse)
def get_html(analysis_id: str) -> str:
    return report.to_html(_get(analysis_id))


@app.get("/v1/analyses/{analysis_id}/report.docx")
def get_docx(analysis_id: str) -> Response:
    return Response(report.to_docx(_get(analysis_id)),
                    media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": f'attachment; filename="assessment-{analysis_id}.docx"'})


@app.get("/v1/rubric")
def rubric() -> list[dict[str, Any]]:
    return report.questions_reference()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")
