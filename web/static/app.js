// processlens UI — upload or pick a sample, read the assessment. Vanilla JS.

const root = document.getElementById("root");
const state = { report: null, selected: null, busy: false, files: { bpmn: null, doc: null } };

// ------------------------------------------------------------------ i18n (EN source strings are the keys)
const PT = {
 "Analyze a process": "Analisar um processo",
 "LangGraph · 8 nodes": "LangGraph · 8 nós",
 "Description": "Descrição",
 "choose file": "escolher arquivo",
 "Run analysis ▸": "Rodar análise ▸",
 "analyzing…": "analisando…",
 "or a synthetic sample": "ou um exemplo sintético",
 "Pipeline run": "Execução do pipeline",
 "model": "modelo",
 "deterministic": "determinístico",
 "Priority matrix": "Matriz de prioridade",
 "impact × feasibility": "impacto × viabilidade",
 "feasibility →": "viabilidade →",
 "↑ impact": "↑ impacto",
 "quick wins": "ganhos rápidos",
 "Candidate": "Candidata",
 "Impact": "Impacto",
 "Feasibility": "Viabilidade",
 "Quadrant": "Quadrante",
 "Evidence — verified to exist": "Evidências — verificadas",
 "Questionnaire → rubric": "Questionário → rubrica",
 "Critic & traceability notes": "Notas da crítica e da rastreabilidade",
 "Process": "Processo",
 "Upload a BPMN and its description, or run a sample.": "Envie um BPMN e sua descrição, ou rode um exemplo.",
 "Models propose and answer; code verifies evidence and computes every score.": "O modelo propõe e responde; o código verifica as evidências e calcula cada nota.",
 "process automation agents": "agentes de automação de processos",
 "Quick win": "Ganho rápido",
 "Strategic": "Estratégico",
 "Fill-in": "Complementar",
 "Reconsider": "Reconsiderar",
 "tasks": "tarefas",
 "manual": "manuais",
 "hand-offs": "passagens",
 "sentences": "sentenças",
 "month": "mês",
 "min / case": "min / caso",
 "survived": "sobreviveram",
 "of": "de",
 "Candidates": "Candidatas",
 "A human decision stays human; the system can pre-assemble the evidence and a recommendation.": "Decisão humana continua humana; o sistema pode reunir as evidências e uma recomendação.",
 "Field extraction from PDFs is a solved document-AI task with confidence scores and human review.": "Extrair campos de PDFs é tarefa resolvida de IA documental, com nível de confiança e revisão humana.",
 "Classification into a small fixed set of categories suits an LLM or a small classifier.": "Classificar num conjunto pequeno e fixo de categorias combina com um LLM ou um classificador leve.",
 "The check follows written criteria, so it can be expressed as deterministic rules.": "A conferência segue critérios escritos, então pode virar regras determinísticas.",
 "Re-typing data into a system of record is better replaced by an integration.": "Redigitar dados num sistema é melhor substituído por uma integração.",
 "Repetitive UI steps on stable screens are a fit for RPA.": "Passos repetitivos em telas estáveis combinam com RPA.",
 "Templated messages triggered by a state change are trivial to automate.": "Mensagens padronizadas disparadas por mudança de estado são triviais de automatizar.",
 "blocker": "bloqueio",
 "warning": "alerta",
 "info": "info"
};
let lang = (() => { try { return localStorage.getItem("lang"); } catch { return null; } })()
  || ((navigator.language || "").toLowerCase().startsWith("pt") ? "pt" : "en");
const t = (s) => (lang === "pt" && PT[s]) || s;
function setLang(l) { lang = l; try { localStorage.setItem("lang", l); } catch {} document.documentElement.lang = l === "pt" ? "pt-BR" : "en"; render(); }

Object.assign(PT, {
  volume: "volume", time_per_case: "tempo por caso", compliance_risk: "risco de conformidade", rule_based: "baseado em regras",
  digital_input: "entrada digital", system_access: "acesso ao sistema", exception_rate: "taxa de exceção", stability: "estabilidade",
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

const QUAD = { quick_win: ["Quick win", "chip ok"], strategic: ["Strategic", "chip violet"], fill_in: ["Fill-in", "chip warn"], reconsider: ["Reconsider", "chip bad"] };
const LLM_STAGES = new Set(["generate", "critic", "questionnaire"]);

// ------------------------------------------------------------------ pieces

function picker(kind, label, accept) {
  const input = h("input", { type: "file", accept, style: "display:none", onchange: (e) => { state.files[kind] = e.target.files[0]; render(); } });
  const f = state.files[kind];
  return h("label", { class: "drop" + (f ? " has" : "") }, input,
    h("div", { class: "label" }, label), h("div", { class: "mono", style: "margin-top:6px" }, f ? f.name : t("choose file")));
}

function intake() {
  return h("section", { class: "card" },
    h("header", {}, h("span", { class: "label" }, t("Analyze a process")), h("span", { class: "chip violet" }, t("LangGraph · 8 nodes"))),
    h("div", { class: "body stack" },
      h("div", { class: "grid two", style: "gap:10px" }, picker("bpmn", "BPMN 2.0", ".bpmn,.xml"), picker("doc", t("Description"), ".md,.txt,.pdf")),
      h("button", { class: "btn primary", disabled: !(state.files.bpmn && state.files.doc) || state.busy, onclick: upload }, state.busy ? t("analyzing…") : t("Run analysis ▸")),
      h("div", { class: "row" }, h("span", { class: "label" }, t("or a synthetic sample")),
        h("button", { class: "btn", onclick: () => sample("invoice-intake"), disabled: state.busy }, "invoice intake · EN"),
        h("button", { class: "btn", onclick: () => sample("reembolso-viagem"), disabled: state.busy }, "reembolso · PT"))));
}

function pipeline(r) {
  return h("section", { class: "card" }, h("header", {}, h("span", { class: "label" }, t("Pipeline run")),
    h("span", { class: "row" }, h("span", { class: "chip violet" }, t("model")), h("span", { class: "chip ok" }, t("deterministic")))),
    h("div", { class: "pipeline" }, r.timings.map((t) => h("div", { class: "stage " + (LLM_STAGES.has(t.stage) ? "llm" : "rule") },
      h("div", { class: "label" }, t.stage.replace("_", " ")), h("div", { class: "n" }, `${t.ms} ms`)))));
}

function matrix(r) {
  const taken = {};
  const place = (c) => {  // candidates with identical scores are fanned out instead of stacked
    const key = `${c.score.feasibility.toFixed(2)}|${c.score.impact.toFixed(2)}`;
    const n = (taken[key] = (taken[key] ?? -1) + 1);
    return `left:calc(${(4 + c.score.feasibility * 92).toFixed(1)}% + ${n * 34}px);bottom:${(4 + c.score.impact * 88).toFixed(1)}%`;
  };
  return h("section", { class: "card" }, h("header", {}, h("span", { class: "label" }, t("Priority matrix")), h("span", { class: "muted mono" }, t("impact × feasibility"))),
    h("div", { class: "body" }, h("div", { class: "matrix" },
      h("span", { class: "ax", style: "right:10px;bottom:8px" }, t("feasibility →")),
      h("span", { class: "ax", style: "left:10px;top:8px" }, t("↑ impact")),
      h("span", { class: "ax", style: "right:10px;top:8px;color:var(--accent)" }, t("quick wins")),
      r.candidates.map((c) => h("span", {
        class: `mdot ${c.score.quadrant}`, title: c.title,
        style: place(c),
        onclick: () => { state.selected = c.id; render(); },
      }, c.id)))));
}

function table(r) {
  return h("section", { class: "card scroll" }, h("header", {}, h("span", { class: "label" }, `${t("Candidates")} · ${r.candidates.length} ${t("of")} ${r.proposed} ${t("survived")}`)),
    h("table", {}, h("thead", {}, h("tr", {}, ["#", t("Candidate"), t("Impact"), t("Feasibility"), t("Quadrant")].map((c) => h("th", {}, c)))),
      h("tbody", {}, r.candidates.map((c) => h("tr", { class: "clickable" + (c.id === state.selected ? " active" : ""), onclick: () => { state.selected = c.id; render(); } },
        h("td", { class: "mono" }, c.id),
        h("td", {}, h("div", {}, c.title.split(": ").slice(1).join(": ")), h("div", { class: "hash" }, c.title.split(": ")[0])),
        h("td", {}, h("div", { class: "bar" }, h("i", { style: `width:${c.score.impact * 100}%` })), h("span", { class: "hash" }, c.score.impact.toFixed(2))),
        h("td", {}, h("div", { class: "bar" }, h("i", { style: `width:${c.score.feasibility * 100}%` })), h("span", { class: "hash" }, c.score.feasibility.toFixed(2))),
        h("td", {}, h("span", { class: QUAD[c.score.quadrant][1] }, t(QUAD[c.score.quadrant][0]))))))));
}

function detail(r) {
  const c = r.candidates.find((x) => x.id === state.selected);
  if (!c) return null;
  const issues = r.issues.filter((i) => i.candidate_id === c.id);
  return h("section", { class: "card" },
    h("header", {}, h("div", {}, h("div", { class: "label" }, `${c.id} · ${c.technique}`), h("b", {}, c.title)),
      h("span", { class: QUAD[c.score.quadrant][1] }, t(QUAD[c.score.quadrant][0]))),
    h("div", { class: "body stack" },
      h("p", { class: "muted", style: "margin:0" }, t(c.rationale)),
      h("div", { class: "label" }, t("Evidence — verified to exist")),
      c.evidence.map((e) => h("div", { class: "row", style: "align-items:flex-start" }, h("span", { class: e.source === "bpmn" ? "chip violet" : "chip ok" }, `${e.source}:${e.ref}`), h("q", {}, e.quote))),
      h("div", { class: "label", style: "margin-top:6px" }, t("Questionnaire → rubric")),
      h("table", {}, h("tbody", {}, c.score.answers.map((a) => h("tr", {},
        h("td", { class: "mono" }, t(a.question)),
        h("td", {}, h("span", { class: a.answer === "NI" ? "chip bad" : a.answer === "high" ? "chip ok" : "chip" }, t(a.answer))),
        h("td", { class: "mono", title: a.evidence_ref ? r.sentences[a.evidence_ref] : "" }, a.evidence_ref || "—"),
        h("td", { class: "muted" }, tj(a.justification)),
        h("td", { class: "hash" }, `+${(c.score.breakdown[a.question] ?? 0).toFixed(2)}`))))),
      issues.length ? h("div", { class: "stack" }, issues.map((i) => h("div", { class: "row" }, h("span", { class: i.severity === "blocker" ? "chip bad" : i.severity === "warning" ? "chip warn" : "chip" }, t(i.severity)), h("span", { class: "muted" }, i.message)))) : null));
}

function notes(r) {
  const global = r.issues.filter((i) => i.stage !== "audit" || !i.candidate_id);
  if (!global.length) return null;
  return h("section", { class: "card" }, h("header", {}, h("span", { class: "label" }, t("Critic & traceability notes"))),
    h("div", { class: "body stack" }, global.map((i) => h("div", { class: "row" }, h("span", { class: i.severity === "blocker" ? "chip bad" : "chip warn" }, i.stage), h("span", { class: "mono" }, i.candidate_id || ""), h("span", { class: "muted" }, i.message)))));
}

function render() {
  const r = state.report;
  root.replaceChildren(h("div", { class: "main" },
    h("div", { class: "topbar" },
      h("div", { class: "row", style: "gap:14px" }, h("div", { class: "brand-mark" }, h("i"), h("i"), h("i"), h("i")),
        h("div", {}, h("div", { class: "label" }, t("process automation agents")), h("h1", {}, "processlens"))),
      h("div", { class: "row" }, langToggle(), r ? h("div", { class: "row" }, ["html", "md", "docx"].map((f) => h("a", { class: "btn", href: `/v1/analyses/${r.id}/report.${f}`, target: "_blank" }, `.${f}`)),
        h("a", { class: "btn ghost", href: `/v1/analyses/${r.id}`, target: "_blank" }, ".json")) : null)),
    h("div", { class: "content" },
      h("div", { class: "grid split", style: "grid-template-columns:360px minmax(0,1fr)" },
        h("div", { class: "stack", style: "gap:20px" }, intake(),
          r ? h("section", { class: "card" }, h("header", {}, h("span", { class: "label" }, t("Process"))), h("div", { class: "body stack" },
            h("b", {}, r.process.name),
            h("div", { class: "meta-row" }, h("span", { class: "chip" }, `${r.process.tasks} ${t("tasks")}`), h("span", { class: "chip" }, `${r.process.manual_tasks} ${t("manual")}`),
              h("span", { class: "chip" }, `${r.process.handoffs} ${t("hand-offs")}`), h("span", { class: "chip" }, `${r.document.sentences} ${t("sentences")}`)),
            h("div", { class: "meta-row" }, h("span", { class: "chip ok" }, `${r.document.facts.monthly_volume ?? "NI"} / ${t("month")}`),
              h("span", { class: "chip ok" }, `${r.document.facts.minutes_per_case ?? "NI"} ${t("min / case")}`)),
            h("div", { class: "meta-row" }, r.document.facts.systems.map((s) => h("span", { class: "chip violet" }, s))))) : null,
          r ? notes(r) : null),
        r ? h("div", { class: "stack", style: "gap:20px" }, pipeline(r),
          h("div", { class: "grid", style: "grid-template-columns:340px minmax(0,1fr);align-items:start" }, matrix(r), table(r)), detail(r))
          : h("section", { class: "card empty" }, h("p", {}, t("Upload a BPMN and its description, or run a sample.")),
            h("p", { class: "muted" }, t("Models propose and answer; code verifies evidence and computes every score.")))))));
}

render();
