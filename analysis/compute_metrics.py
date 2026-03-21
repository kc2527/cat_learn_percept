#!/usr/bin/env python3
"""Aggregate cat_learn_percept trial CSV files into PA and CP summaries."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def ensure_columns(df: pd.DataFrame, defaults: dict) -> pd.DataFrame:
    out = df.copy()
    for col, val in defaults.items():
        if col not in out.columns:
            out[col] = val
    return out


def read_csvs(input_dir: Path) -> pd.DataFrame:
    files = sorted(input_dir.glob('*.csv'))
    if not files:
        raise FileNotFoundError(f'No CSV files found in {input_dir}')
    return pd.concat([pd.read_csv(f) for f in files], ignore_index=True)


def _main_rows(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if 'trial_type' in out.columns:
        out = out[out['trial_type'] == 'main']
    return out


def summarize_acuity(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    acuity = df[df['mode'] == 'acuity_map_2afc'].copy()
    if acuity.empty:
        return pd.DataFrame(), pd.DataFrame()
    acuity = _main_rows(acuity)
    acuity = ensure_columns(
        acuity,
        {
            'design': 'unknown',
            'u': np.nan,
            'v': np.nan,
            'grid_x': np.nan,
            'grid_y': np.nan,
            'axis_type': 'unknown',
            'sc_reversals': np.nan,
            'sc_trials_done': np.nan,
            'sc_delta_next': np.nan,
            'sc_id': 'missing_sc',
        },
    )

    for col in ['participant', 'session', 'day', 'design']:
        if col in acuity.columns:
            acuity[col] = acuity[col].astype(str)

    keys = ['participant', 'session', 'day', 'design', 'sc_id']
    final_rows = (
        acuity.sort_values(keys + ['trial_index'])
        .groupby(keys, as_index=False)
        .tail(1)
    )

    by_point = final_rows.groupby(
        ['participant', 'session', 'day', 'design', 'u', 'v', 'grid_x', 'grid_y', 'axis_type'],
        as_index=False,
    ).agg(
        threshold=('sc_delta_next', 'mean'),
        reversals=('sc_reversals', 'mean'),
        trials=('sc_trials_done', 'mean'),
        accuracy=('correct', 'mean'),
    )

    wide = by_point.pivot_table(
        index=['participant', 'session', 'day', 'design', 'u', 'v', 'grid_x', 'grid_y'],
        columns='axis_type',
        values='threshold',
        aggfunc='first',
    ).reset_index()
    wide.columns.name = None
    if {'normal', 'tangential'}.issubset(wide.columns):
        wide['anisotropy_normal_over_tangential'] = wide['normal'] / wide['tangential'].clip(lower=1e-6)

    strata = wide.copy()
    if 'v' in strata.columns:
        strata['space_stratum'] = np.where(np.isclose(strata['v'], 0.0), 'boundary_ridge', 'nonboundary_map')

    strata_summary = strata.groupby(
        ['participant', 'session', 'day', 'design', 'space_stratum'], as_index=False
    ).agg(
        mean_normal=('normal', 'mean') if 'normal' in strata.columns else ('u', 'count'),
        mean_tangential=('tangential', 'mean') if 'tangential' in strata.columns else ('u', 'count'),
        mean_anisotropy=('anisotropy_normal_over_tangential', 'mean')
        if 'anisotropy_normal_over_tangential' in strata.columns
        else ('u', 'count'),
        n_points=('u', 'count'),
    )

    return by_point, strata_summary


def summarize_cp(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    cp = df[df['mode'] == 'cp_probe'].copy()
    if cp.empty:
        return pd.DataFrame(), pd.DataFrame()
    cp = _main_rows(cp)
    cp = ensure_columns(
        cp,
        {
            'design': 'unknown',
            'pair_type': 'unknown',
            'band': 'unknown',
            'distance': np.nan,
            'rt_ms': np.nan,
        },
    )

    for col in ['participant', 'session', 'day', 'design']:
        if col in cp.columns:
            cp[col] = cp[col].astype(str)

    by_cond = cp.groupby(
        ['participant', 'session', 'day', 'design', 'pair_type', 'band', 'distance'], as_index=False
    ).agg(
        accuracy=('correct', 'mean'),
        n_trials=('correct', 'size'),
        mean_rt_ms=('rt_ms', 'mean'),
    )

    cp_key = ['participant', 'session', 'day', 'design', 'distance']
    across = by_cond[(by_cond['pair_type'] == 'across') & (by_cond['band'] == 'near')][cp_key + ['accuracy']]
    across = across.rename(columns={'accuracy': 'acc_across'})

    within_near = by_cond[(by_cond['pair_type'] == 'within') & (by_cond['band'] == 'near')][cp_key + ['accuracy']]
    within_near = within_near.rename(columns={'accuracy': 'acc_within_near'})

    within_far = by_cond[(by_cond['pair_type'] == 'within') & (by_cond['band'] == 'far')][cp_key + ['accuracy']]
    within_far = within_far.rename(columns={'accuracy': 'acc_within_far'})

    merged = across.merge(within_near, on=cp_key, how='outer').merge(within_far, on=cp_key, how='outer')
    merged['cp_primary_across_minus_within_near'] = merged['acc_across'] - merged['acc_within_near']
    merged['cp_secondary_within_near_minus_far'] = merged['acc_within_near'] - merged['acc_within_far']

    return by_cond, merged


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--input-dir', type=Path, required=True)
    parser.add_argument('--out-dir', type=Path, required=True)
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    df = read_csvs(args.input_dir)

    acuity_point, acuity_strata = summarize_acuity(df)
    cp_by_cond, cp_contrast = summarize_cp(df)

    if not acuity_point.empty:
        acuity_point.to_csv(args.out_dir / 'pa_by_point_axis.csv', index=False)
    if not acuity_strata.empty:
        acuity_strata.to_csv(args.out_dir / 'pa_strata_summary.csv', index=False)
    if not cp_by_cond.empty:
        cp_by_cond.to_csv(args.out_dir / 'cp_by_condition.csv', index=False)
    if not cp_contrast.empty:
        cp_contrast.to_csv(args.out_dir / 'cp_primary_secondary_contrasts.csv', index=False)

    print(f'Wrote summaries to {args.out_dir}')


if __name__ == '__main__':
    main()
