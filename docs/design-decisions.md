# Design decisions

## Planted patterns (answer key)

These patterns are deliberately built into the synthetic data so that
questions about it have a known correct answer. Without them the data is
noise and "which supplier is worst" has no defensible ground truth.

All figures are **measured from the production data**, not intended targets.
Re-measure with `backend/db/verify_data.py` after any generator edit.

**Trend** — SUP-003, weld assemblies.
PPM climbs across the final 6 months: 899 → 1,049 → 1,039 → 1,360 → 1,672 →
1,586, against a baseline of roughly 334-750. Models welding electrode tip
wear beyond the dressing interval — gradual degradation, not a single event.
Documented in 8D-2025-003 (closed) and 8D-2026-011 (open).

Baseline noise reaches 750 PPM in January 2025, so a single trend month
compared against a single baseline month can go either way. Only the
sustained climb distinguishes trend from noise.

**Spike** — PN-1042, Roof Rail Mk2 (roof stamping, supplied by SUP-009).
November 2025: 53 defect events / 120 defect units, against a background of
2-7 events per month. Models a single bad steel coil. Documented in
8D-2025-007.

**Concentration** — D-WLD-01, weld porosity, Critical.
89.2% of occurrences fall on SUP-003's parts (340 of 381). Emerges from
weighted selection rather than a hard rule, so the figure is measured rather
than asserted. Deliberately the same supplier as the trend.

**Measurement artefact** — SUP-001, stampings.
Recorded PPM rises April to June 2026 (746, 856, 854) against a baseline
around 430-570, then returns to baseline in July and August (478, 433).

This is the only planted pattern where **the data is deliberately wrong**.
8D-2026-009 records that the incoming inspection fixture had drifted out of
calibration: supplier CMM data showed the parts conforming, gauge R&R
confirmed the measurement system was at fault, and the recorded PPM for those
months overstates the actual defect rate.

The pairing with SUP-003 is the point. Two suppliers, both showing a PPM
climb in mid-2026, and the correct response is opposite — one needs supplier
corrective action, the other needed a fixture recalibrated. SQL alone cannot
distinguish them because the tables look identical. Only the 8D says which is
which.

One discrepancy worth knowing: the 8D says the rise began in March, but March
2026 (551 PPM) sits inside normal variation. The visible rise is April
onwards. Left as written — a report opened in May describing a trend as
starting in March is how real 8Ds read.

**Low runners** — PN-1006, PN-1023, PN-1031, PN-1044, PN-1050.
400-1,400 units per month against 9,000-80,000 for everything else. Four of
the five record zero defects across all 24 months; PN-1050 records one. This
is what makes absence representable: 119 of 1,200 part-months are
defect-free. It also creates a real trap — a low-runner with 3 defects on 800
units computes to 3,750 PPM and looks like the worst part in the plant, when
three defects on 800 units is statistical noise.

**8D reports** — 13 total, 4 open, 104 chunks after discipline-boundary
chunking. Two pairs matter:

- **SUP-003**: 8D-2025-003 (closed Feb 2025) records weld porosity being
  fixed; 8D-2026-011 (open June 2026) records it recurring and references
  the earlier report.
- **SUP-001**: 8D-2025-012 (closed, real die wear) and 8D-2026-009 (closed,
  measurement artefact). The same supplier with one genuine problem and one
  that was never a problem at all.

## Why defect data alone can mislead

Three distinct ways a PPM figure can be wrong, all of them ordinary in
body-in-white quality work:

1. **Real degradation** — electrode wear, fixture drift, die wear, a
   supplier changing sub-suppliers. The parts genuinely got worse.
2. **Measurement error** — gauge drift. The parts are fine; the
   instrument is wrong. Chasing this as a supplier problem wastes weeks.
3. **Underreporting** — where defect capture is manual, recorded counts can
   be lower than actual counts. Manual entry at the point of inspection is a
   known weakness in defect recording, and it is the one failure mode that
   makes the data wrong deliberately rather than accidentally.

Only the first is a supplier problem. SQL cannot distinguish the three,
because the defect table looks identical in all cases. Separating them
needs a document.

This is the strongest argument for routing to both SQL and documents. Case 2
is built into the data as the SUP-001 artefact and is testable. Case 3
remains reasoning only — no document records underreporting, and inventing
one would mean fabricating an allegation rather than modelling a known
weakness.

## Part naming and vehicle system pairing

Part names and vehicle systems must be paired correctly, not chosen
independently. Random pairing produced contradictions like "Underbody Assy"
filed under Side Panel. Anyone with manufacturing background spots that
immediately, and it undermines the credibility the project depends on.

## Volume scaling by commodity

Monthly build volume varies by commodity: fasteners 55-80k, sealants 30-45k,
stampings 18-26k, weld assemblies 9-14k, low runners 0.4-1.4k.

Deliberate. With uniform volumes, PPM and raw defect count always agree about
who is worst. With this spread they disagree, so "which supplier has the most
defects" and "which supplier has the worst defect rate" have different
correct answers.

## Defect events vs defect units

`defects` rows are defect *events*; each carries a `quantity` of 1-4 units.
So "how many defects" has two valid readings — 4,725 events, more units.
Any question using that phrasing is ambiguous by construction.

## Phase 1 — SQL tool decision

**Decision: query catalogue.** Full reasoning in `spike-text-to-sql.md`.

Text-to-SQL passed the pre-registered reliability threshold 25/25 with zero
silent failures, contradicting the prior that motivated the spike. The
catalogue was chosen anyway, because one question passed by an unsound method
that happened to give the right answer on this data — meaning the detection
was not airtight and the true silent-failure rate could not be bounded.

## Phase 2 — the veto decision

App 1's governance principle was a veto, not a weight: an unapproved source at
distance 0.720, the best semantic match in the whole set, still classified
BRONZE. The question for App 2 was whether that principle transfers.

**It transfers, but not to the conditions it first appeared to fit.**

### Closed 8D reports — no veto

App 1's veto worked because approval status is a property of the *document*.
An unapproved SOP is wrong to cite regardless of what was asked.

A closed 8D is not like that. Its validity depends on the question. It is the
wrong answer to "what is failing now" and exactly the right answer to "has
this happened before." A veto would block correct answers half the time.

That fails the one-filtering-rule principle carried from App 1: a rule that is
right for one question shape and wrong for another is not one rule.

**Instead:** closed 8Ds are retrievable, grouped separately from open ones,
and their status is shown. The reader judges.

Phase 5 showed this does real work rather than being decorative. On the
question "why is SUP-003's weld porosity getting worse", pure similarity
ranks the closed 2025 report (0.2584) ahead of the open 2026 one (0.2728).
Without the grouping, an agent answering a present-tense question would lead
with a problem fixed eighteen months ago.

### Stale PPM data — no veto, and not built

The dataset runs to August 2026 with no gaps, so staleness does not exist in
it. A recency veto would be untestable — the same problem as the absence
question in Phase 1. Not built.

### What does veto: severity combined with recency

Neither alone, but the pair. For a question about current state, a Critical
defect within the last 90 days is admissible; a Minor defect from 18 months
ago is not — regardless of how well it matches.

### The connecting idea across both apps

App 1: an approved-but-less-similar source outranks an unapproved better match.
App 2: a recent Critical defect outranks an older Minor one, whatever the
semantic match says.

Both are the same claim — that a governance property can override a relevance
score. What differs is which property, and App 2's had to be chosen rather
than inherited. Two candidates were rejected for stated reasons: one because
it was question-dependent, one because it was untestable.

## Phase 3 — schema, contract and generator

### Grain

- `production_volume` — one part, one month
- `defects` — one defect event, with `quantity` = units affected
- `reports_8d` — one 8D report

`defects` and `production_volume` are facts; `suppliers`, `parts` and
`defect_codes` are conformed dimensions. It is a star schema.

### 8D disciplines as separate columns

Eight columns rather than one text blob. Phase 5 chunks on discipline
boundaries, and separate columns mean that happens without parsing and
without a chunker splitting mid-discipline. Same insight that took App 1 from
78% to 95% with article-boundary chunking, built into the schema instead of
handled downstream.

### Data contract

`backend/db/contracts.py` validates every generated row with pydantic before
anything is written, plus three dataset-level checks that row validation
cannot see. Nothing reaches the database until all pass.

The contract caught two silent problems on its first runs:

1. **pandas converted `None` to `nan`** in the 8D reports' nullable columns.
   No error at build time; `nan` would have reached Postgres.
2. **Removing the `max(1, ...)` floor did not make absence possible.** Even
   the lowest-volume part expected ~5 defects a month, so zero was
   arithmetically unreachable. That failure led to low-runner parts — a fix
   to the cause rather than the symptom.

## Phase 4 — the SQL tool

Eight parameterised queries in a fixed catalogue. The agent selects one and
extracts parameters; it never writes SQL and never sees SQL.

Two layers of validation, doing different jobs. **Format** — pydantic, with
`Literal` on the query id and regex on every identifier. **Existence** —
checked against the dimension tables, because `SUP-999` passes every regex
and does not exist. Without the second check it returns zero rows and reads
as "this supplier has no defects" rather than "this supplier is not real."

Injection is structurally closed before either layer: parameters bind through
the driver rather than being interpolated into SQL text, so a malicious value
is a string that matches nothing. What validation adds is loud failure rather
than quiet emptiness.

Four distinct failure kinds — `invalid_request`, `unknown_entity`,
`unavailable`, `query_failed`. Collapsing them would itself be a silent
failure: `unknown_entity` and `unavailable` look identical from outside (no
data), but one means the supplier is not real and the other means it could
not be checked.

## Phase 5 — retrieval

Gemini embeddings, no local model. Keeps PyTorch out of the deploy, which
matters on a 512 MB tier. Same approach as App 1.

**Relevance threshold: 0.35 cosine distance.** Measured, not assumed. Across
seven test questions the bands separated cleanly: relevant matches 0.22-0.33,
a question about data that does not exist 0.385-0.388, a wholly off-topic
question 0.452-0.455. 0.35 sits in the gap with margin either side.

Chunking is on 8D discipline boundaries — 13 reports become 104 chunks, one
per populated discipline. The schema was designed for this in Phase 3, so no
parsing is required and no chunk can split mid-discipline.

## Phase 6 — the routing rule

Full rule in `docs/routing-rule.md`, committed before the router existed.

Four labels: SQL, DOCS, BOTH, NEITHER. The test for BOTH is not whether both
sources return something — they almost always do — but whether an answer from
one source alone would be wrong, misleading, or missing its reason.

Scoring gives no partial credit. Routing BOTH when the label is SQL is wrong,
because an agent that always routes BOTH has learned nothing.

## Phase 7 — routing accuracy

**21-22 of 24 across five runs, 87.5-91.7%.** Reported as a range because at
24 questions each item is 4.2 points and three questions flip between runs.
A single run's number would be selecting on noise.

| | correct |
|---|---|
| SQL | 7/7 |
| DOCS | 7/7 |
| NEITHER | 5/5 |
| BOTH | 3-4/5 |

The consistent misses are BOTH04 and BOTH05, both of which flip. Their
routing reasons are defensible every time — the 8D reports genuinely do hold
problem descriptions and closure status. They sit on a boundary the rule
draws ambiguously rather than being errors.

Two changes took it from the 75% baseline:

1. **The BOTH criterion was made bidirectional.** The original prompt
   described what a SQL-only answer would be missing but had no equivalent
   for a DOCS-only answer, so the router answered "where does the explanation
   live?" when the question is "what would a complete answer need?"
   75% to 87.5%, BOTH 1/6 to 4/6, nothing else dropped.

2. **The supplier list was put in the prompt.** Change 1 had caused a
   regression: the router routed a question about SUP-011 — which does not
   exist — to BOTH and claimed SQL held PPM data confirming a spike. A
   confident claim about data that does not exist is worse than the quiet
   miss it replaced. NEITHER went to 5/5.

Two labels were corrected after seeing results, both recorded in
`eval/routing-set.json` with reasoning. The test applied each time: does the
correction improve the system, or only the number? R05 and BOTH06 were label
errors — correcting them changed no code. N03 stayed counted as a miss
because fixing it required a real change, which was then made.

### A bug the trace found

The document tool accepts a `supplier_id` filter and nothing was passing it.
On "why is SUP-003's defect rate getting worse", five of six retrieved
passages came from 8D-2026-009 — the SUP-001 gauge-drift report.
Semantically similar (a PPM rise, a root cause), wrong supplier.

The passage counts looked correct. Only the citations exposed it. That is the
argument for showing provenance rather than summary statistics, and it was
found by building the trace rather than by testing for it.

## Phase 7-8 — routing latency

Measured across five scoring runs and the interactive path: routing takes
4-8 seconds when the Gemini API is responsive and 25-40 seconds when it is
not. The 24-question scoring script has run in two minutes and in ten, with
identical code. The variance is the API, not the agent — the tools take 1-2
seconds throughout.

**Accepted rather than hidden.** Two consequences shaped the build:

The API is split into `/route` and `/tools` rather than one endpoint. The
routing decision is the most interesting thing the agent produces and it is
available several seconds before the tools finish, so the UI shows it
immediately rather than holding it back.

The frontend counts the wait out loud — "deciding — 12.4s" — because dead air
reads as broken and a visible counter reads as working.

Caching the demo questions was considered and rejected. It would make the
demo instant and misleading; the honest version is to say the routing call is
a real API call and let the counter show it.

## Phase 8 — the interface

A single HTML file, no framework. The page makes two fetch calls and renders
a trace; Next.js would have brought a build step and hundreds of megabytes of
node_modules for no benefit the task requires.

**The routing decision is the hero, above the results.** If the answer sits
at the top and the trace is a panel below it, most people read the answer and
never look at the trace — and the depth the project is judged on becomes
invisible.

The assumed date window is printed under every SQL table. The router extracts
a supplier but not a date range, so the frontend supplies one. Hiding that
would be a number with a concealed assumption, which is the exact failure the
project is about.

## Phase 9 — deployment


- **Frontend** — https://supplier-quality-agent.vercel.app
- **Backend** — https://supplier-quality-agent.onrender.com (Render, Singapore)
- **Database** — Neon Postgres 18 (AWS Singapore), pooled endpoint

### Chroma was replaced with pgvector

App 1 used ChromaDB and App 2 started there. A clean install of the deploy
requirements measured **476 MB against Render's 512 MB limit** — 93% of the
budget before adding any application code.

The weight was almost entirely unused: chromadb pulls onnxruntime (80 MB),
kubernetes (81 MB) and grpc (39 MB) as transitive dependencies. None was
needed — embeddings come from Gemini, and Chroma ran in-process rather than
distributed — and none could be declined.

Moving the vectors into Postgres with pgvector dropped the install to
**107 MB**. The migration was verified rather than assumed: the retrieval
test suite returned cosine distances identical to four decimal places, so
behaviour was unchanged and only storage moved.

Two problems disappeared with it. Render's filesystem is ephemeral, so a
Chroma index had to be rebuilt on every deploy and every cold start; vectors
in Postgres do not disappear. And `report_chunks` carries foreign keys to
`reports_8d`, so a chunk cannot outlive the report it came from — a guarantee
Chroma could not give.

The index is still rebuilt by deleting and reinserting rather than upserting,
so it stays a pure function of the reports table.

### Known constraint

Render's free tier spins down after inactivity, adding 50+ seconds to the
first request. Combined with routing latency, a cold demo can take 90 seconds
to first answer. Hitting `/health` a few minutes beforehand avoids it.

### A failure worth recording

The first deploy failed with `ModuleNotFoundError: No module named 'psycopg2'`
— the `DATABASE_URL` set in Render's dashboard began with `postgresql://`
rather than `postgresql+psycopg://`, so SQLAlchemy loaded its default psycopg2
dialect instead of psycopg 3.

Worth noting because nothing was silent: the process died at startup with the
reason named. Had psycopg2 happened to be installed, it would have connected
and worked, and the deployed service would have been running a different
driver from local development without anyone knowing.