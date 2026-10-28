// processlens UI — upload or pick a sample, read the assessment. Vanilla JS.

const root = document.getElementById("root");
const state = { report: null, selected: null, busy: false, files: { bpmn: null, doc: null } };

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
    h("div", { class: "label" }, label), h("div", { class: "mono", style: "margin-top:6px" }, f ? f.name : "choose file"));
}

function intake() {
  return h("section", { class: "card" },
    h("header", {}, h("span", { class: "label" }, "Analyze a process"), h("span", { class: "chip violet" }, "LangGraph · 8 nodes")),
    h("div", { class: "body stack" },
      h("div", { class: "grid two", style: "gap:10px" }, picker("bpmn", "BPMN 2.0", ".bpmn,.xml"), picker("doc", "Description", ".md,.txt,.pdf")),
      h("button", { class: "btn primary", disabled: !(state.files.bpmn && state.files.doc) || state.busy, onclick: upload }, state.busy ? "analyzing…" : "Run analysis ▸"),
      h("div", { class: "row" }, h("span", { class: "label" }, "or a synthetic sample"),
        h("button", { class: "btn", onclick: () => sample("invoice-intake"), disabled: state.busy }, "invoice intake · EN"),
        h("button", { class: "btn", onclick: () => sample("reembolso-viagem"), disabled: state.busy }, "reembolso · PT"))));
}

function pipeline(r) {
  return h("section", { class: "card" }, h("header", {}, h("span", { class: "label" }, "Pipeline run"),
    h("span", { class: "row" }, h("span", { class: "chip violet" }, "model"), h("span", { class: "chip ok" }, "deterministic"))),
    h("div", { class: "pipeline" }, r.timings.map((t) => h("div", { class: "stage " + (LLM_STAGES.has(t.stage) ? "llm" : "rule") },
      h("div", { class: "label" }, t.stage.replace("_", " ")), h("div", { class: "n" }, `${t.ms} ms`)))));
}

function matrix(r) {
  return h("section", { class: "card" }, h("header", {}, h("span", { class: "label" }, "Priority matrix"), h("span", { class: "muted mono" }, "impact × feasibility")),
    h("div", { class: "body" }, h("div", { class: "matrix" },
      h("span", { class: "ax", style: "right:10px;bottom:8px" }, "feasibility →"),
      h("span", { class: "ax", style: "left:10px;top:8px" }, "↑ impact"),
      h("span", { class: "ax", style: "right:10px;top:8px;color:var(--accent)" }, "quick wins"),
      r.candidates.map((c) => h("span", {
        class: `mdot ${c.score.quadrant}`, title: c.title,
        style: `left:${(4 + c.score.feasibility * 92).toFixed(1)}%;bottom:${(4 + c.score.impact * 88).toFixed(1)}%`,
        onclick: () => { state.selected = c.id; render(); },
      }, c.id)))));
}

function table(r) {
  return h("section", { class: "card scroll" }, h("header", {}, h("span", { class: "label" }, `Candidates · ${r.candidates.length} of ${r.proposed} survived`)),
    h("table", {}, h("thead", {}, h("tr", {}, ["#", "Candidate", "Impact", "Feasibility", "Evidence", "Quadrant"].map((c) => h("th", {}, c)))),
      h("tbody", {}, r.candidates.map((c) => h("tr", { class: "clickable" + (c.id === state.selected ? " active" : ""), onclick: () => { state.selected = c.id; render(); } },
        h("td", { class: "mono" }, c.id),
        h("td", {}, h("div", {}, c.title.split(": ").slice(1).join(": ")), h("div", { class: "hash" }, c.title.split(": ")[0])),
        h("td", {}, h("div", { class: "bar" }, h("i", { style: `width:${c.score.impact * 100}%` })), h("span", { class: "hash" }, c.score.impact.toFixed(2))),
        h("td", {}, h("div", { class: "bar" }, h("i", { style: `width:${c.score.feasibility * 100}%` })), h("span", { class: "hash" }, c.score.feasibility.toFixed(2))),
        h("td", { class: "mono" }, `${Math.round(c.score.coverage * 100)}%`),
        h("td", {}, h("span", { class: QUAD[c.score.quadrant][1] }, QUAD[c.score.quadrant][0])))))));
}

function detail(r) {
  const c = r.candidates.find((x) => x.id === state.selected);
  if (!c) return null;
  const issues = r.issues.filter((i) => i.candidate_id === c.id);
  return h("section", { class: "card" },
    h("header", {}, h("div", {}, h("div", { class: "label" }, `${c.id} · ${c.technique}`), h("b", {}, c.title)),
      h("span", { class: QUAD[c.score.quadrant][1] }, QUAD[c.score.quadrant][0])),
    h("div", { class: "body stack" },
      h("p", { class: "muted", style: "margin:0" }, c.rationale),
      h("div", { class: "label" }, "Evidence — verified to exist"),
      c.evidence.map((e) => h("div", { class: "row", style: "align-items:flex-start" }, h("span", { class: e.source === "bpmn" ? "chip violet" : "chip ok" }, `${e.source}:${e.ref}`), h("q", {}, e.quote))),
      h("div", { class: "label", style: "margin-top:6px" }, "Questionnaire → rubric"),
      h("table", {}, h("tbody", {}, c.score.answers.map((a) => h("tr", {},
        h("td", { class: "mono" }, a.question),
        h("td", {}, h("span", { class: a.answer === "NI" ? "chip bad" : a.answer === "high" ? "chip ok" : "chip" }, a.answer)),
        h("td", { class: "mono", title: a.evidence_ref ? r.sentences[a.evidence_ref] : "" }, a.evidence_ref || "—"),
        h("td", { class: "muted" }, a.justification),
        h("td", { class: "hash" }, `+${(c.score.breakdown[a.question] ?? 0).toFixed(2)}`))))),
      issues.length ? h("div", { class: "stack" }, issues.map((i) => h("div", { class: "row" }, h("span", { class: i.severity === "blocker" ? "chip bad" : i.severity === "warning" ? "chip warn" : "chip" }, i.severity), h("span", { class: "muted" }, i.message)))) : null));
}

function notes(r) {
  const global = r.issues.filter((i) => i.stage !== "audit" || !i.candidate_id);
  if (!global.length) return null;
  return h("section", { class: "card" }, h("header", {}, h("span", { class: "label" }, "Critic & traceability notes")),
    h("div", { class: "body stack" }, global.map((i) => h("div", { class: "row" }, h("span", { class: i.severity === "blocker" ? "chip bad" : "chip warn" }, i.stage), h("span", { class: "mono" }, i.candidate_id || ""), h("span", { class: "muted" }, i.message)))));
}

function render() {
  const r = state.report;
  root.replaceChildren(h("div", { class: "main" },
    h("div", { class: "topbar" },
      h("div", { class: "row", style: "gap:14px" }, h("div", { class: "brand-mark" }, h("i"), h("i"), h("i"), h("i")),
        h("div", {}, h("div", { class: "label" }, "process automation agents"), h("h1", {}, "processlens"))),
      r ? h("div", { class: "row" }, ["html", "md", "docx"].map((f) => h("a", { class: "btn", href: `/v1/analyses/${r.id}/report.${f}`, target: "_blank" }, `.${f}`)),
        h("a", { class: "btn ghost", href: `/v1/analyses/${r.id}`, target: "_blank" }, ".json")) : null),
    h("div", { class: "content" },
      h("div", { class: "grid split", style: "grid-template-columns:360px minmax(0,1fr)" },
        h("div", { class: "stack", style: "gap:20px" }, intake(),
          r ? h("section", { class: "card" }, h("header", {}, h("span", { class: "label" }, "Process")), h("div", { class: "body stack" },
            h("b", {}, r.process.name),
            h("div", { class: "meta-row" }, h("span", { class: "chip" }, `${r.process.tasks} tasks`), h("span", { class: "chip" }, `${r.process.manual_tasks} manual`),
              h("span", { class: "chip" }, `${r.process.handoffs} hand-offs`), h("span", { class: "chip" }, `${r.document.sentences} sentences`)),
            h("div", { class: "meta-row" }, h("span", { class: "chip ok" }, `${r.document.facts.monthly_volume ?? "NI"} / month`),
              h("span", { class: "chip ok" }, `${r.document.facts.minutes_per_case ?? "NI"} min / case`)),
            h("div", { class: "meta-row" }, r.document.facts.systems.map((s) => h("span", { class: "chip violet" }, s))))) : null,
          r ? notes(r) : null),
        r ? h("div", { class: "stack", style: "gap:20px" }, pipeline(r), h("div", { class: "grid two" }, matrix(r), detail(r)), table(r))
          : h("section", { class: "card empty" }, h("p", {}, "Upload a BPMN and its description, or run a sample."),
            h("p", { class: "muted" }, "Models propose and answer; code verifies evidence and computes every score."))))));
}

render();
