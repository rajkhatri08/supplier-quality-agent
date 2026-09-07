# Design decisions

## Planted patterns (answer key)

These patterns are deliberately built into the synthetic data so that
questions about it have a known correct answer. Without them the data is
noise and "which supplier is worst" has no defensible ground truth.

All figures are **measured from the production data**, not intended targets.
Adding the gauge-drift artefact changed the random stream, so every figure
below was re-measured after that change. Re-measure with
`backend/db/verify_data.py` after any generator edit.

**Trend** — SUP-003, weld assemblies.
PPM climbs across the final 6 months: 899 → 1,049 → 1,039 → 1,360 → 1,672 →
1,586, against a baseline of roughly 334-750. Models welding electrode tip
wear beyond the dressing interval — gradual degradation, not a single event.
Documented in 8D-2025-003 (closed) and 8D-2026-011 (open).

Note that baseline noise reaches 750 PPM in January 2025, so a single trend
month compared against a single baseline month can go either way. Only the
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
starting in March is how real 8Ds read, and the approximation is realistic
rather than an error.

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
  the earlier report. Makes the Phase 2 status decision demonstrable.
- **SUP-001**: 8D-2025-012 (closed, real die wear) and 8D-2026-009 (closed,
  measurement artefact). The same supplier with one genuine problem and one
  that was never a problem at all.

## Why defect data alone can mislead

From a month on a body-in-white line doing root-cause analysis, three
distinct ways a PPM figure can be wrong:

1. **Real degradation** — electrode wear, fixture drift, die wear, a
   supplier changing sub-suppliers. The parts genuinely got worse.
2. **Measurement error** — gauge drift. The parts are fine; the
   instrument is wrong. Chasing this as a supplier problem wastes weeks.
3. **Underreporting** — I saw manual defect capture where recorded counts
   were lower than actual counts. The data is wrong on purpose.

Only the first is a supplier problem. SQL cannot distinguish the three,
because the defect table looks identical in all cases. Separating them
needs a document: an audit note, an 8D, a gauge R&R record.

This is the strongest argument for routing to both SQL and documents. Case 2
is now built into the data as the SUP-001 artefact and is testable. Case 3
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

This is deliberate. With uniform volumes, PPM and raw defect count always
agree about who is worst. With this spread they disagree, so "which supplier
has the most defects" and "which supplier has the worst defect rate" have
different correct answers.

## Defect events vs defect units

`defects` rows are defect *events*; each carries a `quantity` of 1-4 units.
So "how many defects" has two valid readings — 4,725 events, more units.
Any question using that phrasing is ambiguous by construction, and the
routing eval set must be explicit about which is meant.

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

## Phase 5 — retrieval

Gemini embeddings, Chroma storage, no local model. Keeps PyTorch out of the
deploy, which matters on a 512 MB tier.

**Relevance threshold: 0.35 cosine distance.** Measured, not assumed. Across
seven test questions the bands separated cleanly: relevant matches 0.22-0.33,
a question about data that does not exist 0.385-0.388, a wholly off-topic
question 0.452-0.455. 0.35 sits in the gap with margin either side.

**Known Phase 9 constraint.** chromadb pulls onnxruntime (80 MB), kubernetes
(81 MB) and grpc (39 MB) as transitive dependencies. None is used —
embeddings come from Gemini, and Chroma runs in-process. They cannot be
declined. Deploy and dev requirements are split to keep pandas (72 MB) out of
the deployed slug. If Render rejects the build at 512 MB, moving to pgvector
in Postgres is the fix and removes all 200 MB.

Chroma's index is also ephemeral on Render — the filesystem resets on every
deploy. The index rebuilds from Postgres at startup, which takes seconds for
104 chunks, and rebuild is the normal path rather than a recovery path so the
deployed behaviour is the behaviour that gets tested.