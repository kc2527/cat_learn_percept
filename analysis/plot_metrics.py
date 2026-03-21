#!/usr/bin/env python3
"""Create PA/CP diagnostic plots for cat_learn_percept sessions."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ANGLE_COLORS = {45: '#1f77b4', 135: '#d62728', 0: '#2ca02c', 90: '#ff7f0e'}


def _interval_changed(row: pd.Series, prefix: str, eps: float = 1e-9) -> bool:
    dx = abs(float(row[f'{prefix}a_x']) - float(row[f'{prefix}b_x']))
    dy = abs(float(row[f'{prefix}a_y']) - float(row[f'{prefix}b_y']))
    return (dx + dy) > eps


def _main_rows(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if 'trial_type' in out.columns:
        out = out[out['trial_type'] == 'main']
    return out


def plot_pa_profiles(df: pd.DataFrame, out_dir: Path, title: str) -> list[Path]:
    out = []
    pa = _main_rows(df[df['mode'] == 'acuity_map_2afc'].copy())
    if pa.empty:
        return out
    if 'axis_type' not in pa.columns:
        if 'angle_deg' in pa.columns:
            pa['axis_type'] = np.where(np.isclose(pa['angle_deg'], 135), 'normal', 'tangential')
        else:
            pa['axis_type'] = 'unknown'
    if 'u' not in pa.columns:
        pa['u'] = np.nan
    if 'v' not in pa.columns:
        pa['v'] = np.nan

    final_rows = (
        pa.sort_values(['sc_id', 'trial_index'])
        .groupby('sc_id', as_index=False)
        .tail(1)
    )

    by_axis = final_rows.groupby('axis_type', as_index=False)['sc_delta_next'].mean()
    fig, ax = plt.subplots(figsize=(5.2, 4.2))
    ax.bar(by_axis['axis_type'], by_axis['sc_delta_next'], color=['#1f77b4', '#d62728'])
    ax.set_ylabel('Threshold proxy (sc_delta_next)')
    ax.set_title(f'{title}\nPA axis thresholds')
    ax.grid(axis='y', alpha=0.3)
    fig.tight_layout()
    p = out_dir / 'pa_axis_thresholds.png'
    fig.savefig(p, dpi=160)
    plt.close(fig)
    out.append(p)

    if {'u', 'v', 'axis_type'}.issubset(final_rows.columns):
        pivot = final_rows.pivot_table(
            index=['u', 'v'], columns='axis_type', values='sc_delta_next', aggfunc='first'
        ).reset_index()
        if {'normal', 'tangential'}.issubset(pivot.columns):
            pivot['anisotropy'] = pivot['normal'] / pivot['tangential'].clip(lower=1e-6)
            fig, ax = plt.subplots(figsize=(6.0, 4.8))
            sc = ax.scatter(pivot['u'], pivot['v'], c=pivot['anisotropy'], s=120, cmap='viridis')
            cb = plt.colorbar(sc, ax=ax)
            cb.set_label('normal / tangential')
            ax.axhline(0, color='#6b7280', ls='--', lw=1)
            ax.set_xlabel('u (tangential)')
            ax.set_ylabel('v (normal; 0 = boundary ridge)')
            ax.set_title(f'{title}\nPA anisotropy map')
            ax.grid(alpha=0.25)
            fig.tight_layout()
            p = out_dir / 'pa_anisotropy_map.png'
            fig.savefig(p, dpi=160)
            plt.close(fig)
            out.append(p)

            strata = pivot.assign(space_stratum=np.where(np.isclose(pivot['v'], 0.0), 'boundary_ridge', 'nonboundary_map'))
            ss = strata.groupby('space_stratum', as_index=False)['anisotropy'].mean()
            fig, ax = plt.subplots(figsize=(5.2, 4.2))
            ax.bar(ss['space_stratum'], ss['anisotropy'], color=['#7c3aed', '#0ea5e9'])
            ax.set_ylabel('Mean anisotropy')
            ax.set_title(f'{title}\nBoundary vs nonboundary (PA)')
            ax.grid(axis='y', alpha=0.3)
            fig.tight_layout()
            p = out_dir / 'pa_boundary_vs_nonboundary.png'
            fig.savefig(p, dpi=160)
            plt.close(fig)
            out.append(p)

    return out


def plot_cp_profiles(df: pd.DataFrame, out_dir: Path, title: str) -> list[Path]:
    out = []
    cp = _main_rows(df[df['mode'] == 'cp_probe'].copy())
    if cp.empty:
        return out

    by_cond = cp.groupby(['pair_type', 'band', 'distance'], as_index=False).agg(
        acc=('correct', 'mean'), n=('correct', 'size')
    )

    fig, ax = plt.subplots(figsize=(6.8, 4.6))
    for (pair_type, band), sub in by_cond.groupby(['pair_type', 'band']):
        sub = sub.sort_values('distance')
        label = f'{pair_type}_{band}'
        ax.plot(sub['distance'], sub['acc'], '-o', lw=2, ms=5, label=label)
    ax.axhline(0.5, color='#6b7280', ls='--', lw=1)
    ax.set_ylim(0, 1)
    ax.set_xlabel('Distance')
    ax.set_ylabel('Accuracy')
    ax.set_title(f'{title}\nCP condition profiles')
    ax.legend(frameon=False)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    p = out_dir / 'cp_condition_profiles.png'
    fig.savefig(p, dpi=160)
    plt.close(fig)
    out.append(p)

    contrasts = []
    for d in sorted(by_cond['distance'].unique()):
        acc_across = by_cond[(by_cond['pair_type'] == 'across') & (by_cond['band'] == 'near') & (by_cond['distance'] == d)]['acc']
        acc_within_near = by_cond[(by_cond['pair_type'] == 'within') & (by_cond['band'] == 'near') & (by_cond['distance'] == d)]['acc']
        acc_within_far = by_cond[(by_cond['pair_type'] == 'within') & (by_cond['band'] == 'far') & (by_cond['distance'] == d)]['acc']
        if len(acc_across) and len(acc_within_near):
            contrasts.append({'distance': d, 'metric': 'across - within_near', 'value': float(acc_across.iloc[0] - acc_within_near.iloc[0])})
        if len(acc_within_near) and len(acc_within_far):
            contrasts.append({'distance': d, 'metric': 'within_near - within_far', 'value': float(acc_within_near.iloc[0] - acc_within_far.iloc[0])})

    if contrasts:
        cdf = pd.DataFrame(contrasts)
        fig, ax = plt.subplots(figsize=(6.8, 4.6))
        for metric, sub in cdf.groupby('metric'):
            sub = sub.sort_values('distance')
            ax.plot(sub['distance'], sub['value'], '-o', lw=2, ms=5, label=metric)
        ax.axhline(0, color='#6b7280', ls='--', lw=1)
        ax.set_xlabel('Distance')
        ax.set_ylabel('Contrast value')
        ax.set_title(f'{title}\nCP primary/secondary contrasts')
        ax.legend(frameon=False)
        ax.grid(alpha=0.25)
        fig.tight_layout()
        p = out_dir / 'cp_primary_secondary_contrasts.png'
        fig.savefig(p, dpi=160)
        plt.close(fig)
        out.append(p)

    return out


def validate_interval_structure(df: pd.DataFrame) -> dict:
    required = {'i1a_x', 'i1a_y', 'i1b_x', 'i1b_y', 'i2a_x', 'i2a_y', 'i2b_x', 'i2b_y'}
    if not required.issubset(df.columns):
        return {'checked': False}

    c1 = df.apply(lambda r: _interval_changed(r, 'i1'), axis=1)
    c2 = df.apply(lambda r: _interval_changed(r, 'i2'), axis=1)
    out = {
        'checked': True,
        'n_rows': int(len(df)),
        'exactly_one': int((c1 ^ c2).sum()),
        'both': int((c1 & c2).sum()),
        'none': int(((~c1) & (~c2)).sum()),
    }
    if 'diff_interval' in df.columns:
        interval = np.where(c1, 1, np.where(c2, 2, np.nan))
        out['label_match'] = int(np.nansum(interval == df['diff_interval'].to_numpy()))
        out['label_mismatch'] = int(np.nansum((interval != df['diff_interval'].to_numpy()) & ~np.isnan(interval)))
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--input-csv', type=Path, required=True)
    parser.add_argument('--out-dir', type=Path, required=True)
    parser.add_argument('--title', type=str, default='cat_learn_percept')
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(args.input_csv)

    paths = []
    paths.extend(plot_pa_profiles(df, args.out_dir, args.title))
    paths.extend(plot_cp_profiles(df, args.out_dir, args.title))

    summary = {
        'rows_total': int(len(df)),
        'rows_pa': int((df['mode'] == 'acuity_map_2afc').sum()) if 'mode' in df.columns else 0,
        'rows_cp': int((df['mode'] == 'cp_probe').sum()) if 'mode' in df.columns else 0,
        'interval_check': validate_interval_structure(df),
    }

    (args.out_dir / 'summary.txt').write_text(
        '\n'.join([
            f"rows_total={summary['rows_total']}",
            f"rows_pa={summary['rows_pa']}",
            f"rows_cp={summary['rows_cp']}",
            f"interval_check={summary['interval_check']}",
        ]) + '\n',
        encoding='utf-8',
    )

    print('Wrote:')
    for p in paths:
        print(p)
    print(args.out_dir / 'summary.txt')


if __name__ == '__main__':
    main()
