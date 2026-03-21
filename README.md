# cat_learn_percept

Standalone PsychoJS experiment for perceptual assessment in II category-learning studies.

## Project ownership and handoff

- PI/owner: you (initial design + protocol decisions)
- Maintainer-in-training: grad student (day-to-day development and run operations)
- Handoff docs:
  - `docs/HANDOFF.md`
  - `docs/PA_protocol.md`
  - `docs/CP_protocol.md`

## Local serving

Use the provided `Makefile`:

```bash
make serve
```

Optional:

```bash
make serve-open
make launch
make serve PORT=9000
```

Stop server with `Ctrl+C`.

## Start here (new lab member)

1. Read `docs/HANDOFF.md`.
2. Start local server (`make serve-open`).
3. Run one PA session (`mode=acuity_map_2afc`) and one CP session (`mode=cp_probe`).
4. Inspect geometry in `space_viewer.html`.
5. Export CSV and run `analysis/compute_metrics.py`.

## Runtime modes

Set mode and design through URL params:

- `mode=cp_probe` (EEG day)
- `mode=acuity_map_2afc` (PA day)
- `mode=space_viewer` (interactive mapping viewer)
- `design=full|pilot` (default recommended: `full`)

Common params:

- `participant=###`
- `session=###`
- `day=baseline|post1|post2|unspecified`
- `seed=<optional deterministic seed>`
- `debug_preview=1` (optional; PA mode only, shows last trial's 4 stimuli before next trial)
- `cat_axis_gap=<float>` (distance between category major axes)
- `cat_major_axis_frac=<float>` (major-axis length as fraction of space diagonal)
- `cat_minor_axis_len=<float>` (shared minor-axis length)
- `pa_axis_offsets=<a,b>` (2 axis offsets for PA in-category points)
- `pa_outer_offsets=<a,b>` (outer offsets for PA out-of-category probe lines)
- `cp_dist_small=<float>` and `cp_dist_large=<float>` (CP matched distances)

Current default geometry (shared across viewer panels):

- `cat_axis_gap=30`
- `cat_major_axis_frac=0.75`
- `cat_minor_axis_len=25`
- category viewer sample count default: `300`

Example URLs:

- `index.html?mode=cp_probe&design=full&participant=077&session=006&day=post1`
- `index.html?mode=acuity_map_2afc&design=full&participant=077&session=007&day=post2`
- `space_viewer.html?mode=space_viewer`
- `space_viewer.html?cat_axis_gap=30&cat_major_axis_frac=0.75&cat_minor_axis_len=25&pa_axis_offsets=-18,18&pa_outer_offsets=10,18&cp_dist_small=6&cp_dist_large=12`

## Controls

- `space`: start block / continue after break
- `1` / `2`: 2IFC response (which interval had within-interval change)
- `escape`: quit

## Full design summary

- `cp_probe` + `design=full`:
  - 24 practice trials + balanced main trials across within-category and between-category conditions
  - CP pair geometry in viewer:
    - within-A: small and large pairs centered on category A centroid, parallel to major axis
    - within-B: small and large pairs centered on category B centroid, parallel to major axis
    - between: two boundary locations, each with small and large cross-boundary pairs
  - break after 100 main trials
- `acuity_map_2afc` + `design=full`:
  - probe template derived from shared categories:
    - 2 inside points per category on major axis (`pa_axis_offsets`)
    - corresponding outside points per category on boundary-normal lines (`pa_outer_offsets`)
  - 2 axes per point (`tangential=45`, `normal=135`)
  - adaptive staircases, stop rule: `reversals>=3` or `trials>=8`
  - midpoint break

## Launcher

Use `launcher.html` to start sessions without manually editing URL params.

- Fill participant/session/day/mode/design (+ optional seed)
- Click `Launch Here` or `Launch New Tab`
- `Copy URL` copies the resolved launch link to clipboard
- If `mode=space_viewer`, launcher opens `space_viewer.html` directly.

Launcher also stores the most recent form state in browser local storage.

## Interactive space viewer

Open `space_viewer.html` to inspect the category boundary and grating mapping.

- Three dedicated panels with separate controls and plots:
- `Underlying categories`
- `PA Probe Locations`
- `CP Pair Geometry`
- Shared ellipse shape controls are in `Underlying categories` and apply to all panels
- Each panel includes a right-side grating render at that panel's current mouse coordinates
- Panel controls map directly to URL params for reproducibility

## Offline summaries

Aggregate exported trial CSV files:

```bash
python3 analysis/compute_metrics.py --input-dir <csv_dir> --out-dir <summary_dir>
```

Outputs:

- `pa_by_point_axis.csv`
- `pa_strata_summary.csv`
- `cp_by_condition.csv`
- `cp_primary_secondary_contrasts.csv`

## Diagnostic plots

Generate PA/CP diagnostics from one CSV:

```bash
python3 analysis/plot_metrics.py \
  --input-csv <trial_csv_file> \
  --out-dir <plot_output_dir> \
  --title "<participant/session label>"
```

Possible outputs (depends on mode rows in input):

- `pa_axis_thresholds.png`
- `pa_anisotropy_map.png`
- `pa_boundary_vs_nonboundary.png`
- `cp_condition_profiles.png`
- `cp_primary_secondary_contrasts.png`
- `summary.txt`

## Project cleanup conventions

- Python cache and generated analysis artifacts are ignored via `.gitignore`
- `analysis/plots/` and `analysis/data/*.csv` are treated as run outputs, not source
- Keep committed source limited to experiment/runtime code and analysis scripts

## Development workflow

- Create feature branches: `feature/<name>`, `fix/<name>`, `docs/<name>`
- Open PRs for non-trivial changes
- Keep commits small and protocol-linked (reference PA/CP section changed)
