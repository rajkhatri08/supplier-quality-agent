# Design decisions

## Planted patterns (spike answer key)

These three patterns are deliberately built into the synthetic data so the
Phase 1 spike questions have a known correct answer. Without them the data is
noise and "which supplier is worst" has no defensible ground truth.

**Trend** — SUP-003, weld assemblies.
PPM rises steadily across the last 6 months of the 24-month window,
roughly 300 to 730 PPM. Represents a degrading weld fixture.

**Spike** — PN-1042, underbody stamping.
Normal months around 5 defects, one month around 40.
Represents a single bad steel coil.

**Concentration** — D-WLD-01, weld porosity.
About 70% of all occurrences fall on SUP-003's parts.
Deliberately the same supplier as the trend, so "worst weld porosity"
and "who is trending worse" point at the same place.
