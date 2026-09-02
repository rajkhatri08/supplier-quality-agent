# Design decisions

## Planted patterns (spike answer key)

These three patterns are deliberately built into the synthetic data so the
Phase 1 spike questions have a known correct answer. Without them the data is
noise and "which supplier is worst" has no defensible ground truth.

**Trend** — SUP-003, weld assemblies.
PPM rises steadily across the last 6 months of the 24-month window,
roughly 300 to 730 PPM. Models welding electrodes wearing down between
replacement intervals: a gradual degradation, not a single event.

**Spike** — PN-1042, a rocker panel (side panel stamping, supplied by SUP-009).
Normal months around 5 defects, one month around 40.
Models a single bad steel coil entering the line.

**Concentration** — D-WLD-01, weld porosity.
About 70% of all occurrences fall on SUP-003's parts.
Deliberately the same supplier as the trend, so "worst weld porosity"
and "who is trending worse" point at the same place.

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