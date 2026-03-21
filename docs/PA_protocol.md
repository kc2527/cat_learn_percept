# Perceptual Acuity (PA) Protocol

## Purpose

PA estimates discrimination acuity at controlled locations in the shared stimulus space. The goal is to quantify local sensitivity relative to category geometry and boundary distance.

## Stimulus-space definition

- Coordinate system: `x, y` each in `[0, 100]`.
- Category boundary: line `y = x`.
- Category ellipses:
  - major axis parallel to `y = x`
  - major-axis length = `cat_major_axis_frac * diagonal_length`
  - shared minor-axis length = `cat_minor_axis_len`
  - axis separation between category centroids controlled by `cat_axis_gap`

These geometry parameters are shared with CP and visualized in `space_viewer.html`.

## Probe placement rules

- Inside-category anchor points:
  - defined by `pa_axis_offsets=<a,b>` along the major axis for each category.
- Outside-category points:
  - for each inside anchor, create a paired outside line using `pa_outer_offsets=<u,v>` along the boundary-normal direction.
- Result:
  - matched probe families around each category side with controllable distance from boundary.

## Trial structure (2IFC)

- Two intervals are shown.
- Observer responds with `1` or `2` for the interval containing the within-interval change.
- Key controls:
  - `space`: continue/start
  - `1` / `2`: response
  - `escape`: quit

## Adaptive logic and stopping

- Staircases are run by probe point and axis condition.
- Stop rule (current full design): `reversals >= 3` OR `trials >= 8`.
- Midpoint break enabled in full design.

## Parameters to treat as protocol-level controls

- Shared geometry: `cat_axis_gap`, `cat_major_axis_frac`, `cat_minor_axis_len`
- PA-specific geometry: `pa_axis_offsets`, `pa_outer_offsets`
- Session metadata: `participant`, `session`, `day`, `seed`

Current defaults used in viewer:

- `cat_axis_gap=30`
- `cat_major_axis_frac=0.75`
- `cat_minor_axis_len=25`
- `pa_axis_offsets=-18,18`
- `pa_outer_offsets=10,18`

## Outputs and interpretation

Primary analysis outputs:

- `pa_by_point_axis.csv`
- `pa_strata_summary.csv`

Diagnostic plots can include:

- `pa_axis_thresholds.png`
- `pa_anisotropy_map.png`
- `pa_boundary_vs_nonboundary.png`

Interpretation focus:

- threshold differences by axis (`tangential` vs `normal`)
- threshold differences by boundary proximity and category side
- consistency across sessions/days

## Rationale for this design

- Shared category geometry ensures PA and CP are directly comparable.
- Inside/outside matched probe families allow sensitivity mapping relative to category boundary structure.
- Axis-specific staircases isolate directional acuity effects without changing global category layout.
