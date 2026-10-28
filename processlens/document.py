"""Process description (Markdown, text or PDF) → numbered sentences + extracted facts.

Sentences get stable ids (S1, S2, …) so every later claim can cite one. The
facts are regex/lexicon based — cheap, explainable, and good enough to ground
the questionnaire; the model is asked to *cite*, not to *remember*.
"""
from __future__ import annotations

import io
import re
import unicodedata

from processlens.schemas import DocumentFacts, ProcessDocument, Sentence

KNOWN_SYSTEMS = ["SAP", "ERP", "CRM", "SharePoint", "Excel", "e-mail", "Outlook", "Teams", "Salesforce", "Oracle",
                 "planilha", "portal", "SEI", "intranet", "Jira", "ServiceNow"]

# signal → words that indicate it (accent-folded, lowercase; PT + EN)
SIGNALS = {
    "manual": ["manual", "manually", "by hand", "digita", "redigita", "copia", "copy", "type", "retype", "key in"],
    "paper": ["paper", "papel", "printed", "impresso", "scan", "digitaliza"],
    "structured": ["form", "formulario", "xml", "json", "api", "structured", "estruturad", "csv"],
    "unstructured": ["pdf", "e-mail", "email", "anexo", "attachment", "free text", "texto livre"],
    "rules": ["rule", "regra", "policy", "politica", "threshold", "limite", "checklist", "criteria", "criterio"],
    "exceptions": ["exception", "excecao", "rework", "retrabalho", "devolv", "returned", "error", "erro", "inconsist"],
    "stable": ["stable", "estavel", "has not changed", "nao mudou", "standard", "padronizad"],
    "changing": ["changes often", "muda com frequencia", "frequently changes", "new rules every"],
    "compliance": ["audit", "auditoria", "compliance", "conformidade", "legal", "fraud", "fraude", "regulat"],
    "api": ["api", "webservice", "web service", "integration", "integracao"],
}
_VOLUME = re.compile(r"(?:~|about|around|cerca de|aprox\.?|approximately)?\s*(\d[\d.,]*)\s*"
                     r"(?:requests|invoices|cases|claims|pedidos|notas|solicitacoes|processos|casos)\s*"
                     r"(?:per|por|a|/)\s*(month|mes|week|semana|day|dia)", re.I)
_MINUTES = re.compile(r"(\d+)\s*(?:min|minutes|minutos)\b", re.I)
_HOURS = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:h|hours|horas)\b(?!\w)", re.I)


def fold(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def _split(text: str) -> list[tuple[str, str]]:
    """(section, sentence) pairs. Headings start sections; bullets are sentences."""
    section, out = "Overview", []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            section = line.lstrip("# ").strip() or section
            continue
        line = re.sub(r"^[-*•]\s+|^\d+[.)]\s+", "", line)
        for sent in re.split(r"(?<=[.!?;])\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ0-9])", line):
            if len(sent.strip()) > 3:
                out.append((section, sent.strip()))
    return out


def _numbers(raw: str) -> int:
    """'1,200' / '1.200' (thousands) → 1200; '2,5' / '2.5' (decimal) → 2."""
    raw = raw.rstrip(".,")
    if re.fullmatch(r"\d{1,3}([.,]\d{3})+", raw):
        return int(re.sub(r"[.,]", "", raw))
    return int(float(raw.replace(",", ".")))


def extract_facts(sentences: list[Sentence]) -> DocumentFacts:
    facts = DocumentFacts()
    for s in sentences:
        f = fold(s.text)
        for signal, words in SIGNALS.items():
            if any(w in f for w in words):
                facts.mentions.setdefault(signal, []).append(s.id)
        if facts.monthly_volume is None and (m := _VOLUME.search(f)):
            n, per = _numbers(m.group(1)), m.group(2)
            facts.monthly_volume = n * {"month": 1, "mes": 1, "week": 4, "semana": 4, "day": 21, "dia": 21}[per]
            facts.mentions.setdefault("volume", []).append(s.id)
        if facts.minutes_per_case is None and (m := _MINUTES.search(f)):
            facts.minutes_per_case = int(m.group(1))
            facts.mentions.setdefault("time", []).append(s.id)
        elif facts.minutes_per_case is None and (m := _HOURS.search(f)):
            facts.minutes_per_case = int(float(m.group(1).replace(",", ".")) * 60)
            facts.mentions.setdefault("time", []).append(s.id)
        for system in KNOWN_SYSTEMS:
            if re.search(rf"(?<![\w-]){re.escape(fold(system))}(?![\w-])", f) and system not in facts.systems:
                facts.systems.append(system)
    return facts


def from_text(text: str, title: str | None = None) -> ProcessDocument:
    pairs = _split(text)
    sentences = [Sentence(id=f"S{i}", section=sec, text=t) for i, (sec, t) in enumerate(pairs, 1)]
    if not sentences:
        raise ValueError("the description has no readable sentences")
    heading = next((ln.lstrip("# ").strip() for ln in text.splitlines() if ln.startswith("# ")), None)
    return ProcessDocument(title=title or heading or "Process description", sentences=sentences,
                           facts=extract_facts(sentences))


def from_pdf(data: bytes, title: str | None = None) -> ProcessDocument:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    text = "\n".join((page.extract_text() or "") for page in reader.pages)
    return from_text(text, title)


def load(filename: str, data: bytes) -> ProcessDocument:
    if filename.lower().endswith(".pdf") or data[:5] == b"%PDF-":
        return from_pdf(data)
    return from_text(data.decode("utf-8", errors="replace"))
