// processlens UI — upload or pick a sample, read the assessment. Vanilla JS.

const root = document.getElementById("root");
const state = { report: null, selected: null, busy: false, files: { bpmn: null, doc: null } };

// ------------------------------------------------------------------ i18n (EN source strings are the keys)
const PT = {
 "Automation finder": "Buscador de automações",
 "Send a process diagram (BPMN) and its written description. The AI suggests which steps to automate, and every suggestion has to quote the documents. Anything it can't back up is thrown out.":
   "Envie o diagrama de um processo (BPMN) e a descrição escrita dele. A IA sugere quais etapas automatizar, e cada sugestão precisa citar os documentos. O que ela não consegue comprovar é descartado.",
 "Choose a process": "Escolha um processo",
 "Process diagram (BPMN)": "Diagrama do processo (BPMN)",
 "Written description": "Descrição escrita",
 "choose file": "escolher arquivo",
 "Analyze": "Analisar",
 "analyzing…": "analisando…",
 "Or try an example": "Ou teste com um exemplo",
 "Invoice intake (English)": "Recebimento de notas (inglês)",
 "Travel reimbursement (Portuguese)": "Reembolso de viagem (português)",
 "How the analysis ran": "Como a análise foi feita",
 "AI": "IA",
 "code": "código",
 "Read diagram": "Ler diagrama", "Read text": "Ler texto", "AI suggests": "IA sugere", "AI reviews": "IA revisa",
 "Check sources": "Conferir fontes", "AI answers checklist": "IA responde checklist", "Score": "Nota", "Final check": "Revisão final",
 "Where to start": "Por onde começar",
 "easier to do →": "mais fácil de fazer →",
 "↑ bigger gain": "↑ maior ganho",
 "start here": "comece por aqui",
 "Suggestion": "Sugestão",
 "Gain": "Ganho",
 "Ease": "Facilidade",
 "Verdict": "Veredito",
 "Why": "Por quê",
 "Where the documents say so": "Onde os documentos dizem isso",
 "diagram": "diagrama",
 "text": "texto",
 "How the score was calculated": "Como a nota foi calculada",
 "Points to double-check": "Pontos para conferir",
 "The process": "O processo",
 "Pick an example on the left to see a full analysis in a few seconds.": "Escolha um exemplo à esquerda para ver uma análise completa em poucos segundos.",
 "The AI suggests and answers questions. Plain code checks every quote and calculates every score, so the result can be trusted.":
   "A IA sugere e responde perguntas. Código comum confere cada citação e calcula cada nota, então dá para confiar no resultado.",
 "Download": "Baixar",
 "Start here": "Comece por aqui",
 "Bigger project": "Projeto maior",
 "If there's time": "Se sobrar tempo",
 "Probably not worth it": "Talvez não valha",
 "steps": "etapas",
 "done by hand": "feitas à mão",
 "hand-offs": "passagens de mão",
 "cases / month": "casos / mês",
 "min / case": "min / caso",
 "suggestions kept": "sugestões mantidas",
 "of": "de",
 "Suggestions": "Sugestões",
 "Decision support": "Apoio à decisão", "Document AI": "Leitura de documentos com IA", "LLM triage": "Triagem com IA",
 "Rules engine": "Regras automáticas", "API integration": "Integração por API", "RPA": "Robô de software (RPA)", "Auto-notify": "Aviso automático",
 "A human decision stays human; the system can pre-assemble the evidence and a recommendation.": "Decisão humana continua humana; o sistema pode reunir as evidências e uma recomendação.",
 "Field extraction from PDFs is a solved document-AI task with confidence scores and human review.": "Extrair campos de PDFs é tarefa resolvida de IA documental, com nível de confiança e revisão humana.",
 "Classification into a small fixed set of categories suits an LLM or a small classifier.": "Classificar num conjunto pequeno e fixo de categorias combina com um LLM ou um classificador leve.",
 "The check follows written criteria, so it can be expressed as deterministic rules.": "A conferência segue critérios escritos, então pode virar regras automáticas.",
 "Re-typing data into a system of record is better replaced by an integration.": "Redigitar dados num sistema é melhor substituído por uma integração.",
 "Repetitive UI steps on stable screens are a fit for RPA.": "Passos repetitivos em telas estáveis combinam com um robô de software (RPA).",
 "Templated messages triggered by a state change are trivial to automate.": "Mensagens padronizadas disparadas por mudança de estado são fáceis de automatizar.",
 "blocker": "bloqueio",
 "warning": "atenção",
 "info": "info",
 "critic": "revisão da IA", "trace": "conferência de fontes", "questionnaire": "checklist", "audit": "revisão final",
 "not stated": "não informado"
};
let lang = (() => { try { return localStorage.getItem("lang"); } catch { return null; } })()
  || ((navigator.language || "").toLowerCase().startsWith("pt") ? "pt" : "en");
const t = (s) => (lang === "pt" && PT[s]) || s;
function setLang(l) { lang = l; try { localStorage.setItem("lang", l); } catch {} document.documentElement.lang = l === "pt" ? "pt-BR" : "en"; render(); }

// The checklist questions, in plain words.
const QUESTIONS = {
  volume: ["How often it happens", "Com que frequência acontece"], time_per_case: ["Time spent per case", "Tempo gasto por caso"],
  compliance_risk: ["Risk of compliance errors", "Risco de erro de conformidade"], rule_based: ["Follows clear rules", "Segue regras claras"],
  digital_input: ["Input is already digital", "A entrada já é digital"], system_access: ["Systems can be reached", "Dá para acessar os sistemas"],
  exception_rate: ["How often there are exceptions", "Frequência de exceções"], stability: ["The process is stable", "O processo é estável"],
};
const question = (q) => (QUESTIONS[q] || [q, q])[lang === "pt" ? 1 : 0];
Object.assign(PT, {
  high: "alta", medium: "média", low: "baixa",
  "the activity is audited": "a atividade é auditada", "no audit signal": "sem sinal de auditoria",
  "explicit criteria are documented": "há critérios explícitos documentados", "no written criteria found": "nenhum critério escrito encontrado",
  "works on data already captured upstream": "usa dados já capturados antes", "needs only read access to data already in hand": "só precisa ler dados já disponíveis",
  "this step consumes PDFs, e-mails or paper": "esta etapa consome PDFs, e-mails ou papel", "inputs arrive as attachments": "as entradas chegam como anexos",
  "inputs are structured": "as entradas são estruturadas", "the system has no API (UI only)": "o sistema não tem API (só interface)",
  "an API exists": "existe uma API", "UI access only": "acesso só pela interface", "rework is reported for this step": "há retrabalho relatado nesta etapa",
  "rework is reported for the process": "há retrabalho relatado no processo", "no rework reported": "nenhum retrabalho relatado",
  "rules are reported stable": "as regras são estáveis", "rules change": "as regras mudam", "not stated in the description": "não consta na descrição",
});
// justifications that carry numbers
function tj(text) {
  if (lang !== "pt") return text;
  let m = text.match(/^about (\S+) cases per month$/);
  if (m) return `cerca de ${m[1]} casos por mês`;
  m = text.match(/^~(\S+) of (\S+) minutes per case sit in this step$/);
  if (m) return `~${m[1].replace(".", ",")} de ${m[2]} minutos por caso estão nesta etapa`;
  return t(text);
}

function langToggle() {
  return h("span", { class: "lang" }, ["en", "pt"].map((l) => h("button", { class: lang === l ? "on" : "", onclick: () => setLang(l) }, l.toUpperCase())));
}


function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "style") el.style.cssText = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}

function toast(msg, bad = false) {
  const t = h("div", { class: "toast" + (bad ? " bad" : "") }, msg);
  document.body.append(t);
  setTimeout(() => t.remove(), 3500);
}

async function call(path, options) {
  state.busy = true; render();
  try {
    const res = await fetch(path, options);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail?.message || JSON.stringify(data.detail));
    state.report = data;
    state.selected = data.candidates[0]?.id || null;
  } catch (e) { toast(e.message, true); }
  state.busy = false; render();
}

const sample = (name) => call(`/v1/samples/${name}`, { method: "POST" });
function upload() {
  const form = new FormData();
  form.append("bpmn_file", state.files.bpmn);
  form.append("description", state.files.doc);
  call("/v1/analyses", { method: "POST", body: form });
}

const QUAD = { quick_win: ["Start here", "chip ok"], strategic: ["Bigger project", "chip violet"], fill_in: ["If there's time", "chip warn"], reconsider: ["Probably not worth it", "chip bad"] };
const TECHNIQUE = { decision_support: "Decision support", document_ai: "Document AI", llm_classification: "LLM triage", rules_engine: "Rules engine",
  api_integration: "API integration", rpa: "RPA", notification: "Auto-notify" };
const STAGES = { parse_bpmn: "Read diagram", read_doc: "Read text", generate: "AI suggests", critic: "AI reviews", trace: "Check sources",
  questionnaire: "AI answers checklist", score: "Score", audit: "Final check" };
const LLM_STAGES = new Set(["generate", "critic", "questionnaire"]);
const technique = (c) => t(TECHNIQUE[c.technique] || c.technique);
const plainTitle = (c) => c.title.split(": ").slice(1).join(": ") || c.title;

// ------------------------------------------------------------------ pieces

function picker(kind, label, accept) {
  const input = h("input", { type: "file", accept, style: "display:none", onchange: (e) => { state.files[kind] = e.target.files[0]; render(); } });
  const f = state.files[kind];
  return h("label", { class: "drop" + (f ? " has" : "") }, input,
    h("div", { style: "font-weight:500" }, label), h("div", { class: "label", style: "margin-top:6px" }, f ? f.name : t("choose file")));
}

function intake() {
  return h("section", { class: "card" },
    h("header", {}, h("span", { class: "label" }, t("Choose a process"))),
    h("div", { class: "body stack" },
      h("div", { class: "label" }, t("Or try an example")),
      h("button", { class: "btn primary", onclick: () => sample(lang === "pt" ? "reembolso-viagem" : "invoice-intake"), disabled: state.busy },
        state.busy ? t("analyzing…") : t(lang === "pt" ? "Travel reimbursement (Portuguese)" : "Invoice intake (English)")),
      h("button", { class: "btn", onclick: () => sample(lang === "pt" ? "invoice-intake" : "reembolso-viagem"), disabled: state.busy },
        t(lang === "pt" ? "Invoice intake (English)" : "Travel reimbursement (Portuguese)")),
      h("div", { class: "grid two", style: "gap:10px;margin-top:8px" },
        picker("bpmn", t("Process diagram (BPMN)"), ".bpmn,.xml"), picker("doc", t("Written description"), ".md,.txt,.pdf")),
      h("button", { class: "btn", disabled: !(state.files.bpmn && state.files.doc) || state.busy, onclick: upload }, t("Analyze"))));
}

function pipeline(r) {
  return h("section", { class: "card" }, h("header", {}, h("span", { class: "label" }, t("How the analysis ran")),
    h("span", { class: "row" }, h("span", { class: "chip violet" }, t("AI")), h("span", { class: "chip ok" }, t("code")))),
    h("div", { class: "pipeline" }, r.timings.map((s) => h("div", { class: "stage " + (LLM_STAGES.has(s.stage) ? "llm" : "rule") },
      h("div", { class: "n" }, t(STAGES[s.stage] || s.stage)), h("div", { class: "label" }, `${s.ms} ms`)))));
}

function matrix(r) {
  const taken = {};
  const place = (c) => {  // candidates with identical scores are fanned out instead of stacked
    const key = `${c.score.feasibility.toFixed(2)}|${c.score.impact.toFixed(2)}`;
    const n = (taken[key] = (taken[key] ?? -1) + 1);
    return `left:calc(${(4 + c.score.feasibility * 92).toFixed(1)}% + ${n * 34}px);bottom:${(4 + c.score.impact * 88).toFixed(1)}%`;
  };
  return h("section", { class: "card" }, h("header", {}, h("span", { class: "label" }, t("Where to start"))),
    h("div", { class: "body" }, h("div", { class: "matrix" },
      h("span", { class: "ax", style: "right:10px;bottom:8px" }, t("easier to do →")),
      h("span", { class: "ax", style: "left:10px;top:8px" }, t("↑ bigger gain")),
      h("span", { class: "ax", style: "right:10px;top:8px;color:var(--accent)" }, t("start here")),
      r.candidates.map((c) => h("span", {
        class: `mdot ${c.score.quadrant}`, title: plainTitle(c),
        style: place(c),
        onclick: () => { state.selected = c.id; render(); },
      }, c.id)))));
}

function table(r) {
  return h("section", { class: "card scroll" }, h("header", {}, h("span", { class: "label" }, t("Suggestions")),
    h("span", { class: "muted" }, `${r.candidates.length} ${t("of")} ${r.proposed} ${t("suggestions kept")}`)),
    h("table", {}, h("thead", {}, h("tr", {}, ["#", t("Suggestion"), t("Gain"), t("Ease"), t("Verdict")].map((c) => h("th", {}, c)))),
      h("tbody", {}, r.candidates.map((c) => h("tr", { class: "clickable" + (c.id === state.selected ? " active" : ""), onclick: () => { state.selected = c.id; render(); } },
        h("td", { class: "muted" }, c.id),
        h("td", {}, h("div", {}, plainTitle(c)), h("div", { class: "label" }, technique(c))),
        h("td", {}, h("div", { class: "bar" }, h("i", { style: `width:${c.score.impact * 100}%` }))),
        h("td", {}, h("div", { class: "bar" }, h("i", { style: `width:${c.score.feasibility * 100}%` }))),
        h("td", {}, h("span", { class: QUAD[c.score.quadrant][1] }, t(QUAD[c.score.quadrant][0]))))))));
}

function detail(r) {
  const c = r.candidates.find((x) => x.id === state.selected);
  if (!c) return null;
  const issues = r.issues.filter((i) => i.candidate_id === c.id);
  return h("section", { class: "card" },
    h("header", {}, h("div", {}, h("div", { class: "label" }, `${t("Suggestion")} ${c.id} · ${technique(c)}`), h("b", { style: "font-size:18px" }, plainTitle(c))),
      h("span", { class: QUAD[c.score.quadrant][1] }, t(QUAD[c.score.quadrant][0]))),
    h("div", { class: "body stack" },
      h("div", { class: "label" }, t("Why")),
      h("p", { style: "margin:0" }, t(c.rationale)),
      h("div", { class: "label", style: "margin-top:8px" }, t("Where the documents say so")),
      c.evidence.map((e) => h("div", { class: "row", style: "align-items:flex-start;flex-wrap:nowrap" },
        h("span", { class: e.source === "bpmn" ? "chip violet" : "chip ok" }, e.source === "bpmn" ? t("diagram") : `${t("text")} ${e.ref}`), h("q", {}, e.quote))),
      h("div", { class: "label", style: "margin-top:8px" }, t("How the score was calculated")),
      h("table", {}, h("tbody", {}, c.score.answers.map((a) => h("tr", {},
        h("td", {}, question(a.question)),
        h("td", {}, h("span", { class: a.answer === "NI" ? "chip bad" : a.answer === "high" ? "chip ok" : "chip" }, a.answer === "NI" ? t("not stated") : t(a.answer))),
        h("td", { class: "muted", title: a.evidence_ref ? r.sentences[a.evidence_ref] : "" }, tj(a.justification)),
        h("td", { class: "muted", style: "text-align:right" }, `+${(c.score.breakdown[a.question] ?? 0).toFixed(2)}`))))),
      issues.length ? h("div", { class: "stack" }, issues.map((i) => h("div", { class: "row" }, h("span", { class: i.severity === "blocker" ? "chip bad" : i.severity === "warning" ? "chip warn" : "chip" }, t(i.severity)), h("span", { class: "muted" }, i.message)))) : null));
}

function notes(r) {
  const global = r.issues.filter((i) => i.stage !== "audit" || !i.candidate_id);
  if (!global.length) return null;
  return h("section", { class: "card" }, h("header", {}, h("span", { class: "label" }, t("Points to double-check"))),
    h("div", { class: "body stack" }, global.map((i) => h("div", { class: "stack", style: "gap:4px" },
      h("div", { class: "row" }, h("span", { class: i.severity === "blocker" ? "chip bad" : "chip warn" }, t(i.stage)), i.candidate_id ? h("span", { class: "muted" }, i.candidate_id) : null),
      h("span", { class: "muted" }, i.message)))));
}

function processCard(r) {
  const f = r.document.facts;
  return h("section", { class: "card" }, h("header", {}, h("span", { class: "label" }, t("The process"))), h("div", { class: "body stack" },
    h("b", { style: "font-size:16px" }, r.process.name),
    h("div", { class: "meta-row" }, h("span", { class: "chip" }, `${r.process.tasks} ${t("steps")}`), h("span", { class: "chip" }, `${r.process.manual_tasks} ${t("done by hand")}`),
      h("span", { class: "chip" }, `${r.process.handoffs} ${t("hand-offs")}`)),
    h("div", { class: "meta-row" }, f.monthly_volume != null ? h("span", { class: "chip ok" }, `${f.monthly_volume} ${t("cases / month")}`) : null,
      f.minutes_per_case != null ? h("span", { class: "chip ok" }, `${f.minutes_per_case} ${t("min / case")}`) : null),
    h("div", { class: "meta-row" }, f.systems.map((s) => h("span", { class: "chip violet" }, s)))));
}

function render() {
  const r = state.report;
  root.replaceChildren(h("div", { class: "main" },
    h("div", { class: "topbar" },
      h("div", { class: "row", style: "gap:14px" }, h("div", { class: "brand-mark" }, h("i"), h("i"), h("i"), h("i")),
        h("div", {}, h("h1", { style: "margin:0" }, "processlens"), h("div", { class: "label" }, t("Automation finder")))),
      h("div", { class: "row" }, r ? h("div", { class: "row" }, h("span", { class: "label" }, t("Download")),
        [["docx", "Word"], ["html", "HTML"], ["md", "Markdown"]].map(([f, name]) => h("a", { class: "btn", href: `/v1/analyses/${r.id}/report.${f}`, target: "_blank" }, name)),
        h("a", { class: "btn ghost", href: `/v1/analyses/${r.id}`, target: "_blank" }, "JSON")) : null, langToggle())),
    h("div", { class: "content" },
      h("p", { class: "intro" }, t("Send a process diagram (BPMN) and its written description. The AI suggests which steps to automate, and every suggestion has to quote the documents. Anything it can't back up is thrown out.")),
      h("div", { class: "grid split", style: "grid-template-columns:340px minmax(0,1fr)" },
        h("div", { class: "stack", style: "gap:20px" }, intake(), r ? processCard(r) : null, r ? notes(r) : null),
        r ? h("div", { class: "stack", style: "gap:20px" },
          h("div", { class: "grid", style: "grid-template-columns:340px minmax(0,1fr);align-items:start" }, matrix(r), table(r)), detail(r), pipeline(r))
          : h("section", { class: "card empty" }, h("p", { style: "color:var(--ink);font-size:17px" }, t("Pick an example on the left to see a full analysis in a few seconds.")),
            h("p", { class: "muted" }, t("The AI suggests and answers questions. Plain code checks every quote and calculates every score, so the result can be trusted.")))))));
}

render();
