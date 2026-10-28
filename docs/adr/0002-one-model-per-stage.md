# ADR 0002 — One model per stage, structured output with bounded repair

**Status:** accepted

## Context
Generation, critique and assessment have different cost/quality trade-offs, and
an auditor running on the same model as the generator tends to agree with it.

## Decision
- A `Router` maps each LLM stage (`generate`, `critic`, `questionnaire`) to its own
  model via `PL_MODEL_<STAGE>`. The recommended setup uses a different model family
  for the critic than for the generator.
- Every call requests JSON matching a Pydantic schema (`response_format: json_schema`).
  The response is validated; on failure the validation errors are sent back and the
  model repairs its own output, at most `max_repairs` times, then the stage fails loudly
  (`StructuredOutputError`). Code fences are tolerated.
- An `OfflineAnalyst` implements the same interface deterministically, so the graph,
  the API and CI run with no network and no key.

## Consequences
- Stages can be upgraded independently and A/B tested per stage.
- Malformed output never reaches business logic; a repair costs one extra call and is
  counted in `Usage.repairs`.
