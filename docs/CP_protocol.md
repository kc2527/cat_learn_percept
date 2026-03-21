# Categorical Perception (CP) Protocol

## Purpose

CP tests whether discriminability differs for within-category vs between-category pairs when pair distances are matched.

## Shared geometry dependency

CP must be defined from the same category geometry used by PA:

- `x, y` in `[0, 100]`
- boundary `y = x`
- category ellipses with shared major-axis orientation and shape controls
- shared controls: `cat_axis_gap`, `cat_major_axis_frac`, `cat_minor_axis_len`

## Pair geometry specification

Current CP geometry in viewer is built as black pair segments only.

Within-category pairs:

- Category A: one small pair and one large pair
- Category B: one small pair and one large pair
- all within-category pairs are parallel to ellipse major axis
- each pair set is centered on the corresponding category centroid

Between-category pairs:

- two distinct boundary-adjacent sets (two major-axis locations)
- each set has one small and one large pair
- between pairs span across category sides (boundary-normal direction)

Distance controls:

- `cp_dist_small`
- `cp_dist_large`

## Trial structure (2IFC)

- Two intervals are shown.
- Observer indicates interval containing the change (`1` or `2`).
- `space` advances/starts, `escape` quits.

## Design-level balancing

For `design=full`, CP should remain balanced across:

- within vs between conditions
- category side where applicable
- distance level (small vs large)

## Parameters to track in each run

- metadata: `participant`, `session`, `day`, `seed`
- mode/design: `mode=cp_probe`, `design=full|pilot`
- geometry and distances: `cat_*`, `cp_dist_small`, `cp_dist_large`

Current defaults in viewer examples:

- `cat_axis_gap=30`
- `cat_major_axis_frac=0.75`
- `cat_minor_axis_len=25`
- `cp_dist_small=6`
- `cp_dist_large=12`

## Outputs and interpretation

Primary analysis outputs:

- `cp_by_condition.csv`
- `cp_primary_secondary_contrasts.csv`

Diagnostic plots can include:

- `cp_condition_profiles.png`
- `cp_primary_secondary_contrasts.png`

Interpretation focus:

- whether between-category discrimination exceeds matched within-category discrimination
- whether effects are stable across the two between-pair sets
- whether distance scaling (small vs large) behaves similarly across conditions

## Rationale for this design

- Matched small/large distances reduce trivial distance confounds.
- Two between-category sets reduce dependence on a single spatial location.
- Centered within-category pairs keep category-internal comparison anchored to category centroids.
