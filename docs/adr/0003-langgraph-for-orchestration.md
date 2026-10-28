# ADR 0003 — LangGraph for orchestration, thin nodes

**Status:** accepted

## Context
The pipeline has a fan-out (BPMN parsing and document reading are independent),
a linear chain of stages, and state that several stages append to (issues, timings).

## Decision
A `StateGraph` with a `TypedDict` state. `issues` and `timings` use additive
reducers (`Annotated[list, operator.add]`) so any node can append without
knowing the others. `parse_bpmn` and `read_doc` start in parallel from `START`
and join before `generate`. Nodes are thin wrappers: each calls one domain
function and returns a partial state; no business rule lives in a node.

## Consequences
- Adding a stage (e.g. an LLM second-opinion auditor) is a node and two edges.
- Every node is unit-testable without the graph; the graph test checks wiring,
  ordering and the parallel branch.
- LangGraph is used for what it is good at — state, wiring, reducers — and not as a
  place to hide logic.
