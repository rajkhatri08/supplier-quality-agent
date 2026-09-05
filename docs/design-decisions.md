# Design decisions

## Planted patterns (spike answer key)

These three patterns are deliberately built into the synthetic data so the
Phase 1 spike questions have a known correct answer. Without them the data is
noise and "which supplier is worst" has no defensible ground truth.

All figures below are **measured from the generated data**, not intended
targets. Where the two differed, the doc was corrected to match the data.

**Trend** — SUP-003, weld assemblies.
PPM climbs across the final 5 months of the 24-month window, roughly 670 to
1,370 against a 400-720 baseline. Models welding electrodes wearing down
between replacement intervals: gradual degradation, not a single event.
The first multiplier month is lost in baseline noise, so a 6-month window is
answerable but a 3-month window would not be.

**Spike** — PN-1042, Roof Rail Mk2 (roof stamping, supplied by SUP-009).
November 2025: 49 defect events / 114 defect units, against a background of
2-7 events per month. Models a single bad steel coil entering the line.

**Concentration** — D-WLD-01, weld porosity, Critical.
86.9% of occurrences fall on SUP-003's parts (318 of 366). Emerges from
weighted selection rather than a hard rule, so the figure is measured rather
than asserted. Deliberately the same supplier as the trend, so "worst weld
porosity" and "who is trending worse" point at the same place.

The pattern IDs are coupled to `build_parts`. Editing that function reshuffles
part assignment and silently invalidates this key. If it moves again, pin the
patterns to a supplier and part *name* rather than an ID.

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

This is the strongest argument for routing to both SQL and documents. It
is recorded here as reasoning, not built into the data — see Phase 6,
where it becomes an eval question that genuinely requires both routes.

## Part naming and vehicle system pairing

Part names and vehicle systems must be paired correctly, not chosen
independently. Random pairing produced contradictions like "Underbody Assy"
filed under Side Panel. Anyone with manufacturing background spots that
immediately, and it undermines the credibility the project depends on.

## Volume scaling by commodity

Monthly build volume varies by commodity: fasteners 55-80k, sealants 30-45k,
stampings 18-26k, weld assemblies 9-14k. Over the last 12 months this gives
SUP-005 4.78M units against SUP-004's 379k — a 12.6x spread.

This is deliberate. With uniform volumes, PPM and raw defect count always
agree about who is worst. With this spread they disagree, so "which supplier
has the most defects" and "which supplier has the worst defect rate" have
different correct answers. That distinction is eval material for Phase 6.

## Defect events vs defect units

`defects` rows are defect *events*; each carries a `quantity` of 1-4 units.
So "how many defects" has two valid readings — 5,023 events, more units.
Any question using that phrasing is ambiguous by construction, and the
routing eval set must be explicit about which is meant.

## Phase 1 — SQL tool decision

**Decision: query catalogue.** Full reasoning in `spike-text-to-sql.md`.

Text-to-SQL passed the pre-registered reliability threshold 25/25 with zero
silent failures, contradicting the prior that motivated the spike. The
catalogue was chosen anyway, because one question passed by an unsound method
that happened to give the right answer on this data — meaning the detection
was not airtight and the true silent-failure rate could not be bounded.

Carried forward: the agent selects a query and extracts parameters; pydantic
validates before anything reaches the database; the tool must be able to
decline rather than return the nearest match.

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

**Instead:** closed 8Ds are retrievable, ranked below open ones, and their
status is shown in the trace. The agent states that a source is a closed 8D
and when it closed. The reader judges.

### Stale PPM data — no veto, and not built

The dataset runs to August 2026 with no gaps, so staleness does not exist in
it. A recency veto would be untestable — the same problem as the absence
question in Phase 1, where a rule could not be demonstrated because the data
could not express the condition.

Building an untestable rule means being unable to show it works. Not built.

### What does veto: severity combined with recency

Neither severity nor recency alone, but the pair. For a question about current
state, a Critical defect within the last 90 days is admissible; a Minor defect
from 18 months ago is not — regardless of how well it matches.

This is testable on the existing data, it is a real quality-engineering rule,
and it preserves governance-as-veto across both apps without forcing a fit
where none exists.

### Schema consequence

- 8D status: indexed and filterable, never a hard filter
- Severity: already a first-class dimension in `defect_codes`
- Recency: derived from `detected_date`, already present

The decision constrains behaviour, not structure. No new columns are required.

### The connecting idea across both apps

App 1: an approved-but-less-similar source outranks an unapproved better match.
App 2: a recent Critical defect outranks an older Minor one, whatever the
semantic match says.

Both are the same claim — that a governance property can override a relevance
score. What differs is which property, and App 2's had to be chosen rather
than inherited. The first two candidates were rejected for stated reasons:
one because it was question-dependent, one because it was untestable.

## Carried into Phase 3

Two generator changes the Phase 1 spike showed are needed:

- allow zero defect events for low-PPM part-months, so absence questions
  become answerable
- give sealants at least one Critical defect code, so severity questions do
  not silently exclude an entire commodity

Also considered for the real schema: `line_station` following the actual BIW
line sequence — docking, underbody, main line, slat line, quality check —
rather than the abstract station labels used in the spike data.