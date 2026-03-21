# Handoff Guide

This document is the operational handoff to the grad student.

## Day 1 checklist

1. Clone repo and install nothing extra (project is static HTML/JS + optional Python analysis).
2. Start server:
   - `make serve-open` (recommended)
   - or `make serve` then open shown URL.
3. Verify launcher works:
   - open `launcher.html`
   - launch one `acuity_map_2afc` and one `cp_probe` session.
4. Verify geometry viewer:
   - open `space_viewer.html`
   - confirm category defaults (`axis_gap=30`, `major_frac=0.75`, `minor_len=25`, `sample_count=300`).
5. Export trial CSV from browser run.
6. Run analysis summary:
   - `python3 analysis/compute_metrics.py --input-dir <csv_dir> --out-dir <summary_dir>`
7. Generate per-run diagnostics:
   - `python3 analysis/plot_metrics.py --input-csv <trial_csv> --out-dir <plot_dir> --title "<participant/session>"`

## Weekly maintenance checklist

1. Confirm `README.md` examples still match runtime behavior.
2. Confirm PA and CP defaults still match viewer and launcher URLs.
3. Spot-check one PA and one CP exported CSV for expected columns and trial counts.
4. Regenerate one diagnostic plot set from a recent run.
5. Open one PR summarizing any protocol or implementation changes.

## Roles and ownership

- PI: approves design changes and protocol changes.
- Grad student: owns implementation updates, testing, and weekly QC checks.
- Shared: both review PA/CP interpretation before changing condition definitions.

## Definition of done for student PRs

A PR is complete only if:

1. Local run path is verified (`make serve-open`, launcher launch, mode starts).
2. Any changed parameter behavior is documented in README and relevant protocol doc.
3. No generated outputs (`analysis/plots`, local CSV payloads) are committed.
4. PR description includes: what changed, why, and how it was tested.
