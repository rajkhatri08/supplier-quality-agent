# Routing ground-truth rule

Written and committed before the router exists. Labelling questions after
seeing what the router does would fit the rubric to the output — the same
failure the Phase 1 threshold was frozen to avoid.

## The three routes

**SQL** — the answer is a number, a ranking, or a set of records computable
from `defects`, `production_volume`, and the dimension tables.

**DOCS** — the answer is an explanation, a cause, an action taken, or a
status recorded in an 8D report.

**BOTH** — neither route alone returns a complete answer.

## What "complete" means

The test is not whether both routes return *something*. Both routes return
something for almost any question — SQL will produce numbers, retrieval will
produce passages above threshold. The test is whether an answer built from
one route alone would be **wrong, misleading, or missing its reason**.

Three cases qualify as BOTH:

1. **A number that needs its cause.** "Why is SUP-003's PPM climbing?" SQL
   shows the climb; only the 8D says electrode tip wear. SQL alone gives a
   trend with no explanation. DOCS alone gives a cause with no evidence it
   is happening.

2. **A claim that needs corroboration.** A PPM figure can be wrong three
   ways: real degradation, gauge drift, or underreporting. SQL cannot
   distinguish them — the defect table looks identical in all three cases.
   Separating them needs a document.

3. **A comparison across both stores.** "Which suppliers with open 8D
   reports have worsening PPM?" The open-report list is in documents; the
   PPM trend is in SQL. Neither half is the answer.

Cases that do NOT qualify:

- A question whose answer is a number, even if an 8D mentions the same
  supplier. Extra context is not incompleteness.
- A question whose answer is an explanation, even if SQL could produce a
  related figure. Supporting data is not incompleteness.
- A question either route answers fully, where the other route happens to
  return something above threshold.

## Ambiguity

If a question is ambiguous about *which metric* — events versus units, rate
versus count — that is not a routing question. It routes to SQL and the
agent states its interpretation. The Phase 1 spike showed the model does
this reliably when permitted to.

## Unanswerable

Questions naming data that does not exist (delivery rates, operator names)
route to **NEITHER**. The correct behaviour is to decline, and both tools
already do: the SQL tool returns `invalid_request` or `unknown_entity`, the
document tool returns `no_match` with the closest distance.

NEITHER is a fourth label, not a failure to label.

## Scoring

A routing decision is correct when it matches the label. Partial credit is
not awarded: routing BOTH when the label is SQL is wrong, because it means
the agent could not tell that one route was sufficient — and an agent that
always routes BOTH has not learned anything.