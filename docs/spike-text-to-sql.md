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
generated SQL runs — by hand-written SQL or pandas. Without that, "0 silent
failures" only means "none I noticed", which is the clean-exit-code trap in
a new costume.

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
    This is where naive SQL starts returning plausible wrong numbers.

Q6  For each commodity, what is the average monthly PPM over the full
    24-month window?
    Tests: same ratio, grouped. Order of operations matters — the average
    of monthly PPMs is not the same as PPM computed from summed totals.

Q7  Which part had the largest single-month increase in defect units
    compared with its own previous month?
    Tests: window function or self-join over an ordered series.

Q8  Which suppliers had a higher total defect count but a lower defect
    PPM than SUP-003 over the last 12 months?
    Tests: both metrics at once, plus comparison against a subquery value.
    A query that answers only one half still returns rows.

Q9  For Critical-severity defects only, which supplier had the worst PPM
    in the final 6 months, and what was it?
    Tests: severity filter on the defect_codes dimension combined with the
    ratio — the filter must apply to the numerator only, never the
    denominator. Filtering both is the classic silent failure here.

Q10 Which parts recorded zero defect events in any month where they had
    production volume above 20,000 units?
    Tests: absence. Requires LEFT JOIN or NOT EXISTS. An INNER JOIN
    returns a clean, confident, completely wrong answer.

Q9 and Q10 are deliberately booby-trapped. Q9 invites filtering the volume
table by severity — meaningless, but it runs and returns an inflated PPM.
Q10 punishes an inner join with a silently truncated result. Both fail
silently, which is the class the threshold treats as disqualifying.

## Expected answers

Computed by hand before any SQL was generated. See
`backend/spike/expected_answers.sql`.

_To be filled in as each is computed._

## Results

_To be filled in after the run. Threshold and questions above are frozen._