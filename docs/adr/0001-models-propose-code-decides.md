# ADR 0001 — Models propose, code decides

**Status:** accepted

## Context
Asking a model "which steps should we automate, and how important is each?"
returns fluent, confident text with three problems: claims that no document
supports, scores that change between runs, and no way to explain a number to
the manager who has to fund the project.

## Decision
Split every judgment into what language models are good at and what they are not:

| Model does | Code does |
|---|---|
| propose candidates and cite evidence | check that every cited element **exists** and the quote **appears** in it (`stages/trace.py`) |
| critique / merge the proposals | apply the critic's decisions mechanically |
| answer a fixed questionnaire with sentence ids, or `NI` | downgrade answers citing non-existent sentences to `NI` |
| — | compute impact and feasibility with published weights (`stages/score.py`) |
| — | audit: flag automated approvals, low evidence coverage, probabilistic steps in audited flows |

## Consequences
- A hallucinated candidate or quote is dropped and *reported* (tested with an
  adversarial provider that invents a candidate and a sentence id).
- Same answers → same score. Scores are explainable line by line (`breakdown`).
- `NI` is first-class: missing information lowers *coverage*, which the auditor
  surfaces, instead of being silently filled by the model.
