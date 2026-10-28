import pytest

from processlens import bpmn, document
from tests.conftest import SAMPLES, make_pdf


def test_bpmn_structure(process):
    assert process.name == "Supplier invoice intake"
    assert process.lanes == ["Accounts Payable", "Budget Owner", "Treasury"]
    assert process.tasks[0].id == "t_receive" and process.tasks[-1].id == "t_notify"   # flow order
    assert process.task("t_approve").lane == "Budget Owner"
    assert process.task("t_schedule").kind == "serviceTask"
    assert process.handoffs == 3
    assert {g.id for g in process.gateways} == {"g_match"}


@pytest.mark.parametrize("payload, message", [
    (b"not xml", "not valid XML"),
    (b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><x/>', "DTDs"),
    (b'<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"/>', "no <bpmn:process>"),
])
def test_bpmn_rejects(payload, message):
    with pytest.raises(bpmn.BpmnError) as exc:
        bpmn.parse(payload)
    assert message in str(exc.value)


def test_document_facts(doc):
    f = doc.facts
    assert f.monthly_volume == 1200 and f.minutes_per_case == 14
    assert {"SAP", "Outlook", "SharePoint"} <= set(f.systems)
    assert {"rules", "exceptions", "api", "compliance", "unstructured"} <= set(f.mentions)
    assert doc.sentences[0].id == "S1" and doc.sentence("S3").section == "Context"


def test_portuguese_document():
    d = document.load("r.md", (SAMPLES / "reembolso-viagem.md").read_bytes())
    assert d.facts.monthly_volume == 250 and d.facts.minutes_per_case == 25
    assert "Excel" in d.facts.systems and "rules" in d.facts.mentions


@pytest.mark.parametrize("raw, expected", [("1,200", 1200), ("1.200", 1200), ("2,5", 2), ("300", 300), ("12.000.000", 12000000)])
def test_number_parsing(raw, expected):
    assert document._numbers(raw) == expected


@pytest.mark.parametrize("text, per_month", [("about 40 requests per week", 160), ("cerca de 10 pedidos por dia", 210)])
def test_volume_units(text, per_month):
    assert document.from_text(text).facts.monthly_volume == per_month


def test_pdf_description():
    pdf = make_pdf(["Expense claims", "We receive about 90 claims per month.", "Each claim takes 12 minutes."])
    d = document.load("claims.pdf", pdf)
    assert d.facts.monthly_volume == 90 and d.facts.minutes_per_case == 12
