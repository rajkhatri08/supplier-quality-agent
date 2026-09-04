# Phase 1 spike — text-to-SQL vs query catalogue

## Question this decides

Does the SQL tool generate queries from natural language, or expose a fixed
catalogue of parameterised queries the agent selects from?

Text-to-SQL sounds more impressive. It also adds a second failure mode — bad
SQL generation — on top of the routing problem that is actually under test.
This spike replaces that reasoning with a number.

## Threshold — written before any query was generated

| Failure type | Definition | Recoverable? |
|---|---|---|
| **Hard** | The generated SQL does not run. Syntax error, wrong column, wrong table. | Yes — catch, retry, or fall back. |
| **Silent** | The SQL runs and returns wrong numbers. | **No.** Nothing flags it. |

**Text-to-SQL wins if:** 0 silent failures AND ≤ 2 hard failures per 10.
**Catalogue wins if:** ≥ 1 silent failure OR ≥ 3 hard failures per 10.

The asymmetry is deliberate. In a quality context a wrong PPM figure that
looks right is worse than no answer at all — it is the exact failure mode the
App 1 governance thesis exists to prevent. Hard failures are tolerable
because they are detectable.

**Numeric tolerance:** an answer within ±1 PPM of the expected value counts as
correct. Registered before the run, so rounding differences are not scored as
failures.

## Sample size — two tiers

A 10-question set with 0 silent failures is consistent with a true silent
failure rate as high as ~26% (95% CI). That is not enough to distinguish a
minor hallucination rate from a systemic flaw.

The expensive part of this spike is not running queries — it is computing
each expected answer independently. So the sample scales only in the branch
where the answer is genuinely in doubt:

- **Tier 1 — 10 questions.** If ≥ 1 silent failure or ≥ 3 hard failures,
  stop. Catalogue wins. No tier 2 needed.
- **Tier 2 — 15 more, harder.** Only if tier 1 passes clean. Decide on all
  25. At 0/25 the upper bound on the silent failure rate falls to ~11%.

## Detection method

Each question's expected answer is computed independently **before** the
generated SQL runs — by hand-written SQL. Without that, "0 silent failures"
only means "none I noticed", which is the clean-exit-code trap in a new
costume.

Writing these by hand surfaced two real instances of the failure class the
spike is designed to catch:

- A first attempt at Q2 grouped `parts` alone instead of joining through
  `defects`. It ran cleanly and returned a system name with a count — but the
  count was parts per system, not defects per system. No error, plausible
  output, wrong answer.
- A transcription error turned 2,144,194 into 12,144,194. Right shape, wrong
  magnitude, caught only because an independent expectation existed to check
  it against.

Both are silent failures produced by hand, which is the argument for the
detection method stated above.

## Question discrimination

A question only tests something if a wrong approach produces a visibly
different answer. Each was checked against the wrong-but-plausible query a
model is likely to produce:

| # | Discriminates? | Evidence |
|---|---|---|
| Q6 | **No** | Average-of-monthly-PPMs and pooled PPM agree to within 0.5 PPM — inside tolerance. Volume noise of ±12% is too narrow for weighting to matter. Kept, and recorded as non-discriminating |
| Q9 | Yes | Filtering the denominator by severity gives 742.88 vs the correct 701.04 — a 6% inflation, well outside tolerance |
| Q10 | Yes | An inner join returns the 2 codes that *were* used instead of the 10 that were not — confident, non-empty, and the opposite of what was asked |

## Findings about the dataset itself

Writing 18 expected answers by hand surfaced three structural properties of
the synthetic data that were not visible from reading the generator. Each was
found by asking a question the data could not properly answer.

### 1. Absence is not representable

The original Q10 asked which parts recorded zero defect events in a month
with production above 20,000 units. The correct answer is empty — but so is
the answer from an inner join, so the question could not discriminate.

Root cause is in the generator:

```python
n_events = rng.randint(max(1, int(expected * 0.4)), max(2, int(expected * 0.9)))
```

The `max(1, ...)` floor guarantees at least one defect event for every
part-month. Confirmed by measurement: 703 part-months exceed 20,000 units,
and **zero** part-months anywhere in the dataset are defect-free.

No question of the form "which X had no Y in period Z" is answerable on this
data. Q10 was replaced with an absence question the data can answer — codes
never used, rather than months never affected.

### 2. No sealant defect code is Critical

D-SLR-01 is Major, D-SLR-02 is Minor. Every other commodity has at least one
Critical code; sealants have none. So SUP-007 and SUP-008 can never record a
Critical defect, and **any Critical-severity question silently excludes an
entire commodity**.

Surfaced by Q14, where both sealant suppliers returned 0.00 Critical PPM and
tied at rank 9. Q15's low Roof share (15.47% vs 46.46% for Front End) is
downstream of the same gap — roof ditch sealer contributes defect units that
can never be Critical.

### 3. A 2x-of-own-average threshold is inside normal variation

Q16 found 36 of 1,200 part-months exceeding twice that part's own 24-month
average. At these count levels — parts averaging 5 to 15 defect units a month
— ordinary variation clears 2x easily. Only PN-1042's planted spike stands
clearly outside, at 7.8x against 2-3x for everything else.

An anomaly rule set at 2x on this data would be mostly false positives. Worth
knowing before any Phase 7 question is phrased in terms of "unusual" months.

### Implication for Phase 3

If the production generator should support absence testing and severity
questions across all commodities, two changes are needed: allow zero events
for low-PPM part-months, and give sealants a Critical code.

## Honesty caveat for the writeup

Even at 25 questions this is a directional signal, not a measurement — the
same limitation already stated about the 23-question eval set in App 1. An
ambiguous result (exactly 1 silent failure) means run more questions, not
pick the preferred answer.

## Tier 1 questions — frozen before generation

Q1  How many defect events were recorded against SUP-003 parts in 2026?
    Tests: join defects to parts, date filter on a year.

Q2  Which vehicle system has the most defect events across the whole window?
    Tests: join, group by a dimension attribute, order, limit.

Q3  What was the total production volume for Weld Assemblies suppliers
    in the last 12 months of the window?
    Tests: two joins, date window, sum on the fact that isn't defects.

Q4  Which defect code appears most often on parts supplied by SUP-009?
    Tests: join, filter on a dimension, group and rank.

Q5  What was SUP-003's defect PPM in August 2026?
    Tests: the ratio. Defect units from one fact table, production units
    from another, joined on part AND month, then scaled by 1,000,000.

Q6  For each commodity, what is the average monthly PPM over the full
    24-month window?
    Tests: two-level aggregation and date alignment. Does not discriminate.

Q7  Which part had the largest single-month increase in defect units
    compared with its own previous month?
    Tests: window function over a partitioned, ordered series. Also NULL
    ordering — Postgres sorts NULLs first under DESC, so NULLS LAST is
    required, not optional.

Q8  Which suppliers had a higher total defect count but a lower defect
    PPM than SUP-003 over the last 12 months?
    "Defect count" is read as SUM(quantity), i.e. defect units.

Q9  For Critical-severity defects only, which supplier had the worst PPM
    in the final 6 months, and what was it?
    Tests: the severity filter must apply to the numerator only. The same
    supplier wins either way — it is the "and what was it" half that
    catches the error.

Q10 Which defect codes were never recorded against any SUP-005 part?
    Tests: absence. An inner join returns the codes that *were* used —
    the exact inverse of the question.

## Expected answers — tier 1

| # | Expected answer | Notes |
|---|---|---|
| Q1 | 295 defect events | ~4.6 events per part-month across 8 parts, 8 months |
| Q2 | Side Panel, 1,315 events | Side Panel 1315, Closures 1133, Roof 934, Underbody 875, Front End 766 — sums to 5,023, confirming the join neither drops nor duplicates rows |
| Q3 | 2,144,194 units | SUP-003 1,183,322 + SUP-010 581,780 + SUP-004 379,092 |
| Q4 | D-STP-01, 296 events | Runners-up 272 / 258 / 247 |
| Q5 | 1369.51 PPM | 133 defect units / 97,115 production units × 1,000,000 |
| Q6 | Weld Assemblies 595.07, Stampings 519.25, Sealants 353.28, Fasteners 184.60 | Pooled reading gives 594.93 / 519.26 / 352.84 / 184.88 — inside tolerance, so both readings score correct |
| Q7 | PN-1042, 2025-11, increase of 104 defect units | The planted spike, and the largest month-over-month jump in the dataset |
| Q8 | SUP-009 | 1,353 defect units at 550.73 PPM vs SUP-003's 954 at 806.20 |
| Q9 | SUP-003, 701.04 PPM | Trap answer, filtering the denominator by severity: 742.88 |
| Q10 | 10 codes — D-SLR-01/02, D-STP-01/02/03/04, D-WLD-01/02/03/04 | Trap answer: the 2 D-FST codes |

### Note on date boundaries

`production_volume.month` stores the first of the month; `defects.detected_date`
stores a specific day. Any query spanning both tables needs
`date_trunc('month', detected_date)::date` to align them. `date_trunc` returns
a timestamp, so the cast matters — without it the join can silently return no
matches, and a `COALESCE(..., 0)` then turns that into a confident zero.

## Tier 1 result and the tier 2 trigger

Tier 1: **10/10 correct, 0 hard failures, 0 silent failures.** Both traps
avoided — Q9 kept severity off the denominator, Q10 used NOT IN against the
full code list. Q5 and Q9 matched the hand-computed values exactly.

This contradicts the prior that motivated the spike. The threshold requires
tier 2, and the decision is not made until all 25 are scored.

Model: `gemini-3.6-flash`. Prompt: raw `schema.sql` DDL plus the question,
with no hints, no worked examples, and no warning about the traps. The DDL
was chosen over a hand-written schema description precisely so no part of the
result could be attributed to prompt tuning.

## Tier 2 — scope and scoring, frozen before questions were written

Tier 1 tested correctness on well-posed questions with computable answers.
That is not what an agent receives. It receives questions that are ambiguous,
unanswerable, or built on a false premise — and a model that writes correct
SQL for the first kind while confidently inventing an answer to the second is
dangerous in a different way.

**Tier 2a — 8 harder well-posed questions.** Multi-level aggregation,
correlated subqueries, ranking within groups. Scored exactly as tier 1.

**Tier 2b — 7 adversarial questions.** Four kinds:

| Kind | Example | Correct behaviour |
|---|---|---|
| Unanswerable | asks for a column the schema does not contain | say it cannot be answered |
| False premise | names an entity that does not exist | say the entity is not present |
| Ambiguous | "how many defects" with no events/units distinction and no window | state the assumption, or ask |
| Wrong grain | daily PPM when volume is monthly | say the grain does not support it |

**Scoring rule, registered before the questions were written:** a confident,
plausible answer to an unanswerable, false-premise, or wrong-grain question
counts as a **silent failure**. It runs clean, it looks right, it is wrong —
the same category the tier 1 threshold already disqualifies.

An ambiguous question is scored correct if the answer states which reading it
took. It is a silent failure if it picks a reading without saying so.

The tier 1 threshold carries over to the full 25: **0 silent failures and
≤ 5 hard failures** for text-to-SQL to win.

Tier 2b feeds Phase 4 regardless of which route wins. Whichever the SQL tool
becomes, it must be able to return "I cannot answer that with the data
available" rather than the closest-looking query. That is the honest
limitation of the catalogue approach, and it turns out to be a requirement
for text-to-SQL too.

## Tier 2 questions

### Tier 2a — well-posed, frozen before generation

Q11  For each commodity, which single part had the worst PPM over the
     last 12 months of the window?
     Tests: ranking within groups. Needs a window function or a
     correlated subquery — a plain ORDER BY returns one part overall,
     not one per commodity, and still returns rows.

Q12  Which parts had a defect PPM above their own supplier's average
     PPM over the full window?
     Tests: a baseline that changes per row. Comparing against the
     global average instead returns a plausible, different set.

Q13  Which suppliers' PPM was worse in the last 12 months than in the
     first 12 months, and by how much?
     Tests: two windows in one query. A query that computes only one
     window still returns suppliers and numbers.

Q14  Ranking suppliers by Critical defects only, how does the order
     differ from ranking them by all defects?
     Tests: two rankings side by side, severity filter on one but not
     the other. Answering only half looks complete.

Q15  For each vehicle system, what share of its defect units came from
     Critical-severity codes?
     Tests: a ratio within a group where numerator and denominator come
     from the same table under different filters. Filtering both gives
     100% everywhere.

Q16  Which part-months had defect units more than double that part's
     own 24-month average?
     Tests: per-part baseline combined with a row-level comparison.
     Using a global average returns a much larger, plausible set.

Q17  Among suppliers with more than 4 parts, which had the lowest PPM
     in the final 6 months?
     Tests: a filter on an aggregate of a dimension, combined with a
     ratio over a window.

Q18  For SUP-003, which defect code accounts for the largest share of
     its defect units, and what percentage is that?
     Tests: a share-of-total within a filtered subset. The denominator
     must be SUP-003's total, not the whole dataset.

### Tier 2b — adversarial, frozen before generation

Q19  What was SUP-003's on-time delivery rate in 2026?
     UNANSWERABLE. No delivery data exists in the schema.

Q20  Why did SUP-011's PPM spike in March 2026?
     FALSE PREMISE. SUP-011 does not exist. Ten suppliers, SUP-001 to SUP-010.

Q21  How many defects did SUP-003 have?
     AMBIGUOUS twice over. Events or units? Over what window?
     Correct: state the reading taken. Silent failure: pick one silently.

Q22  What was PN-1042's PPM on 15 November 2025?
     WRONG GRAIN. Production volume is monthly. Daily PPM is not computable.

Q23  Which operator was working when the D-WLD-01 defects were found?
     UNANSWERABLE. No operator or shift data. `line_station` is a location,
     not a person.

Q24  List the suppliers whose 8D reports are still open.
     FALSE PREMISE for this schema. 8D reports arrive in Phase 5; the spike
     schema has no document table at all.

Q25  Which supplier is the worst?
     AMBIGUOUS on the metric. Highest defect count and worst PPM give
     different answers — Q8 proved that on this data.
     Correct: name the metric chosen. Silent failure: answer without.

Note on the harness: tier 2b needs a different prompt from tier 1. The tier 1
prompt says "return only the SQL query", which forces the model to produce SQL
even when the honest answer is that it cannot. The tier 2b prompt must permit
a non-SQL response, or the test measures the prompt rather than the model.

## Expected answers — tier 2a

Computed by hand before the tier 2 run.

| # | Expected answer | Notes |
|---|---|---|
| Q11 | Weld Assemblies PN-1017 973.12 · Stampings PN-1042 906.56 · Sealants PN-1034 417.66 · Fasteners PN-1026 193.88 | PN-1017 is a SUP-003 weld part carrying the electrode trend. PN-1042 is the planted spike part, still worst in its commodity a year later |
| Q12 | 20 parts of 50, all 10 suppliers represented | PN-1042 has the largest margin over its own supplier average (707.03 vs 548.04). Supplier baselines range from 174 to 661, confirming the partition works |
| Q13 | 6 suppliers worse: SUP-003 +290.99, SUP-002 +78.20, SUP-008 +24.23, SUP-004 +18.14, SUP-009 +7.99, SUP-001 +1.50 | SUP-003's delta is ~4x the next. The planted trend separates cleanly from background noise |
| Q14 | 6 of 10 suppliers change rank. Critical-only order: SUP-003, 004, 010, 009, 001, 002, 005, 006, then 007/008 tied at 9 | SUP-009 drops 2 (one Critical stamping code); SUP-004, 005, 006 each rise 2. SUP-007 and SUP-008 are structurally 0.00 — see dataset finding 2 |
| Q15 | Front End 46.46% · Underbody 40.10% · Closures 35.51% · Side Panel 28.83% · Roof 15.47% | Roof is suppressed by the missing Critical sealant code. Front End is highest because cowl and front apron are weld parts with 2 of 4 codes Critical |
| Q16 | 36 part-months of 1,200 | PN-1042 2025-11 at 114 vs a 14.63 average — 7.8x, against 2-3x for everything else. SUP-003 weld parts (PN-1015 to PN-1019) cluster in 2026 from the trend. A spike shows once and large; a trend shows repeatedly and modest |
| Q17 | SUP-005, 158.41 PPM | Qualifying set is exactly the 5 suppliers with >4 parts: SUP-001, 003, 005, 007, 009. Runners-up 334.08 / 476.31 / 509.20 / 1083.59 — no near-tie |
| Q18 | D-WLD-01, 50.73% | Shares sum to 100%, confirming the denominator is SUP-003's own total. Matches the generator's 3.0-vs-1.0 weighting (3/6). Note: 50.73% is D-WLD-01's share of SUP-003's defects; 86.9% is SUP-003's share of D-WLD-01's occurrences — different ratios, easy to confuse |

### Expected answers — tier 2b

Not numeric. Each is scored on whether the model refuses, flags the false
premise, or states its assumption — per the scoring rule above.

## Results

_Tier 1 recorded above. Tier 2 pending. Final decision pending all 25._