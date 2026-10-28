"""BPMN 2.0 XML → `ProcessModel`. Deterministic, no model involved.

Handles the common shapes exported by Camunda, Bizagi and bpmn.io: tasks of
every flavour, exclusive/parallel gateways, sequence flows and lanes. Anything
else (events, data objects) is ignored on purpose — it does not change what
can be automated.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

from processlens.schemas import Flow, Gateway, ProcessModel, Task

NS = {"bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL"}
TASK_KINDS = ("userTask", "manualTask", "serviceTask", "scriptTask", "sendTask", "receiveTask",
              "businessRuleTask", "task")
GATEWAY_KINDS = ("exclusiveGateway", "parallelGateway", "inclusiveGateway", "eventBasedGateway")
MAX_BYTES = 2_000_000


class BpmnError(ValueError):
    pass


def parse(xml: bytes | str) -> ProcessModel:
    raw = xml.encode() if isinstance(xml, str) else xml
    if len(raw) > MAX_BYTES:
        raise BpmnError("BPMN file too large")
    if b"<!DOCTYPE" in raw[:2000] or b"<!ENTITY" in raw:
        raise BpmnError("DTDs/entities are not accepted")   # XXE / billion-laughs guard
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        raise BpmnError(f"not valid XML: {e}") from e
    process = root.find("bpmn:process", NS)
    if process is None:
        raise BpmnError("no <bpmn:process> element found")

    lane_of: dict[str, str] = {}
    lanes: list[str] = []
    for lane in process.iterfind(".//bpmn:lane", NS):
        name = lane.get("name") or lane.get("id")
        lanes.append(name)
        for ref in lane.iterfind("bpmn:flowNodeRef", NS):
            lane_of[(ref.text or "").strip()] = name

    tasks = [Task(id=el.get("id"), name=(el.get("name") or el.get("id")).strip(), kind=kind, lane=lane_of.get(el.get("id")))
             for kind in TASK_KINDS for el in process.iterfind(f"bpmn:{kind}", NS)]
    gateways = [Gateway(id=el.get("id"), name=el.get("name"), kind=kind)
                for kind in GATEWAY_KINDS for el in process.iterfind(f"bpmn:{kind}", NS)]
    flows = [Flow(id=el.get("id"), source=el.get("sourceRef"), target=el.get("targetRef"), name=el.get("name"))
             for el in process.iterfind("bpmn:sequenceFlow", NS)]
    if not tasks:
        raise BpmnError("the process has no tasks")
    order = {t.id: i for i, t in enumerate(_topological(tasks, flows))}
    tasks.sort(key=lambda t: order.get(t.id, len(order)))
    return ProcessModel(id=process.get("id") or "process", name=process.get("name") or "Unnamed process",
                        tasks=tasks, gateways=gateways, flows=flows, lanes=lanes)


def _topological(tasks: list[Task], flows: list[Flow]) -> list[Task]:
    """Tasks in flow order (best effort; loops are cut), so reports read top to bottom."""
    nxt: dict[str, list[str]] = {}
    indeg: dict[str, int] = {}
    for f in flows:
        nxt.setdefault(f.source, []).append(f.target)
        indeg[f.target] = indeg.get(f.target, 0) + 1
    nodes = {f.source for f in flows} | {f.target for f in flows} | {t.id for t in tasks}
    queue = sorted(n for n in nodes if indeg.get(n, 0) == 0)
    seen, ordered = set(), []
    while queue:
        n = queue.pop(0)
        if n in seen:
            continue
        seen.add(n)
        ordered.append(n)
        for m in nxt.get(n, []):
            indeg[m] -= 1
            if indeg[m] <= 0:
                queue.append(m)
    by_id = {t.id: t for t in tasks}
    return [by_id[n] for n in ordered if n in by_id] + [t for t in tasks if t.id not in seen]
