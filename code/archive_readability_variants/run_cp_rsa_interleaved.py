# -*- coding: utf-8 -*-
"""
Run CP + interleaved RSA protocol (lab mode, PsychoPy).

Design summary:
- CP full with 24 practice + 204 main trials
- RSA points indexed on CP main-trial counts: 1, 52, 103, 154
- RSA uses fixed pool: 49 items x 20 repeats = 980 trials total
- RSA presented as 8 blocks at 500 ms SOA
- EEG trigger pulses + CSV event/trial logging
"""

from datetime import datetime
import csv
import math
import os
import random
import re
import sys
from typing import Dict, List, Tuple
from psychopy import core, event, visual  # type: ignore


# --------------------------- EEG (Parallel Port) helper ---------------------------
EEG_ENABLED = False
EEG_PORT_ADDRESS = '0x3FD8'
EEG_DEFAULT_PULSE_MS = 10

TRIG = {
    # Experiment structure
    'EXP_START': 10,
    'EXP_END': 15,
    # RSA lifecycle
    'RSA_CHUNK1_START': 21,
    'RSA_CHUNK1_END': 22,
    'RSA_READY_ONSET': 23,
    'RSA_CHUNK2_START': 25,
    'RSA_CHUNK2_END': 26,
    # CP lifecycle
    'CP_MAIN_BLOCK_START': 31,
    'CP_MAIN_BLOCK_END': 32,
    'CP_PRACTICE_START': 33,
    'CP_PRACTICE_END': 34,
    # CP trial events
    'CP_ITI_ONSET': 40,
    'CP_INTERVAL1_ONSET': 41,
    'CP_INTERVAL2_ONSET': 42,
    'CP_RESPONSE_PROMPT_ONSET': 43,
    'CP_RESP_1': 44,
    'CP_RESP_2': 45,
    'CP_RESP_TIMEOUT': 46,
    'CP_TRIAL_END': 47,
    'CP_TRIAL_POST_RSA_FLAG': 50,
    # CP condition-coded interval-1 onset triggers (for EEG binning)
    'CP_STIM_WITHIN_A_NEAR': 60,
    'CP_STIM_WITHIN_A_FAR': 61,
    'CP_STIM_WITHIN_B_NEAR': 62,
    'CP_STIM_WITHIN_B_FAR': 63,
    'CP_STIM_ACROSS_NEAR': 64,
    'CP_STIM_ACROSS_FAR': 65,
}

TRIG_NAME_BY_CODE = {v: k for k, v in TRIG.items()}


class EEGPort:

    def __init__(self,
                 win,
                 address=EEG_PORT_ADDRESS,
                 enabled=EEG_ENABLED,
                 default_ms=EEG_DEFAULT_PULSE_MS):
        self.win = win
        self.enabled = enabled
        self.default_ms = default_ms
        self._port = None
        self._clear_at = None
        if not self.enabled:
            return
        try:
            from psychopy import parallel  # type: ignore
            self._port = parallel.ParallelPort(address=address)
        except Exception as e:
            print(f'[EEG] Parallel port unavailable ({e}). Running without triggers.')
            self.enabled = False
            self._port = None

    def flip_pulse(self, code, width_ms=None, global_clock=None):
        if not (self.enabled and self._port):
            return
        width_ms = self.default_ms if width_ms is None else width_ms
        self.win.callOnFlip(self._port.setData, int(code) & 0xFF)
        if global_clock is not None:
            self._clear_at = global_clock.getTime() + (width_ms / 1000.0)

    def pulse_now(self, code, width_ms=None, global_clock=None):
        if not (self.enabled and self._port):
            return
        width_ms = self.default_ms if width_ms is None else width_ms
        self._port.setData(int(code) & 0xFF)
        if global_clock is not None:
            self._clear_at = global_clock.getTime() + (width_ms / 1000.0)

    def update(self, global_clock=None):
        if not (self.enabled and self._port):
            return
        if self._clear_at is not None and global_clock is not None:
            if global_clock.getTime() >= self._clear_at:
                self._port.setData(0)
                self._clear_at = None

    def close(self):
        try:
            if self._port:
                self._port.setData(0)
        except Exception:
            pass


# --------------------------- Protocol constants ----------------------------------
MODE = 'cp_probe'
DESIGN = 'full'

PID_DIGITS = 3
ALLOWED_SUBJECT_IDS = {
    '002', '077', '134', '189', '213', '268', '303', '358', '482',
    '527', '594', '639', '662', '707', '729', '875', '943', '998', '999',
}

CP_PRACTICE_N = 24
CP_MAIN_REPS_PER_CELL = 34
CP_MAIN_RSA_CHECKPOINTS = [1, 52, 103, 154]  # indexed on CP main trials only

RSA_CHUNKS_PER_POINT = 2
RSA_BLOCKS = 8
RSA_POOL_GRID_N = 7  # 7x7 grid
RSA_POOL_SIZE = RSA_POOL_GRID_N * RSA_POOL_GRID_N
RSA_REPEATS_PER_ITEM = 20
RSA_TOTAL_TRIALS = RSA_POOL_SIZE * RSA_REPEATS_PER_ITEM
RSA_SOA_SEC = 0.5
RSA_POOL_SEED = 'rsa_pool_grid7x7_v1'
RSA_POOL_X_MIN = 20.0  # yields min spatial frequency 1.0 cycles/cm under x*5/100 mapping
RSA_POOL_X_MAX = 100.0
RSA_POOL_Y_MIN = 0.0
RSA_POOL_Y_MAX = 100.0

# CP full timing profile (mirrors cat_learn_percept full CP profile)
ITI_SEC = 0.8
ITI_JITTER_SEC = (0.0, 0.4)
INTERVAL_SEC = 0.2
PAIR_GAP_SEC = 0.15
ISI_SEC = 0.4
RESP_WINDOW_SEC = 1.5

# Stimulus space / geometry
X_MIN = 0.0
X_MAX = 100.0
Y_MIN = 0.0
Y_MAX = 100.0
SF_OFFSET = 2.0
SQRT2 = math.sqrt(2)
SPACE_CENTER = (50.0, 50.0)
SPACE_DIAG = math.hypot(X_MAX - X_MIN, Y_MAX - Y_MIN)
T_MAJOR = (1.0 / SQRT2, 1.0 / SQRT2)
N_MINOR = (-1.0 / SQRT2, 1.0 / SQRT2)
# Match run_exp.py spatial-frequency scaling (cycles/cm -> cycles/pixel).
PIXELS_PER_INCH = 227 / 2
PX_PER_CM = PIXELS_PER_INCH / 2.54

# Defaults carried over from viewer/protocol docs
CAT_AXIS_GAP = 30.0
CAT_MAJOR_AXIS_FRAC = 0.75
CAT_MINOR_AXIS_LEN = 25.0
CP_DIST_SMALL = 6.0
CP_DIST_LARGE = 15.0
CP_PRACTICE_FAR_N = 16
CP_PRACTICE_MODERATE_N = 8
CP_PRACTICE_MODERATE_DIST = (CP_DIST_SMALL + CP_DIST_LARGE) * 0.5
PRACTICE_FEEDBACK_SEC = 0.6


# --------------------------- Utility helpers -------------------------------------
def now_iso() -> str:
    return datetime.now().isoformat()


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def dot(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1]


def shift_point(pt: Dict[str, float], direction: Tuple[float, float], amount: float) -> Dict[str, float]:
    return {'x': pt['x'] + direction[0] * amount, 'y': pt['y'] + direction[1] * amount}


def signed_boundary_distance(x: float, y: float) -> float:
    return (y - x) / SQRT2


def in_bounds(x: float, y: float) -> bool:
    return X_MIN <= x <= X_MAX and Y_MIN <= y <= Y_MAX


def to_stim_params(x: float, y: float) -> Tuple[float, float]:
    xt_cycles_per_cm = (x * 5.0) / 100.0
    sf = xt_cycles_per_cm / PX_PER_CM
    ori_deg = (y * 90.0) / 100.0
    return sf, ori_deg


def has_visible_difference(a: Dict[str, float], b: Dict[str, float], eps: float = 1e-9) -> bool:
    return (abs(a['x'] - b['x']) + abs(a['y'] - b['y'])) > eps


def key_to_interval(raw_key: str):
    if raw_key in {'1', 'num_1'}:
        return 1
    if raw_key in {'2', 'num_2'}:
        return 2
    return None


def create_category_geometry():
    major_len = clamp(CAT_MAJOR_AXIS_FRAC, 0.05, 0.95) * SPACE_DIAG
    half_major = major_len * 0.5
    half_minor = clamp(CAT_MINOR_AXIS_LEN * 0.5, 1.0, SPACE_DIAG * 0.45)
    half_gap = CAT_AXIS_GAP * 0.5
    center = {'x': SPACE_CENTER[0], 'y': SPACE_CENTER[1]}
    center_a = shift_point(center, N_MINOR, half_gap)
    center_b = shift_point(center, N_MINOR, -half_gap)
    return {
        'half_major': half_major,
        'half_minor': half_minor,
        'center_a': center_a,
        'center_b': center_b,
    }


def point_on_category_side(pt: Dict[str, float], category: str) -> bool:
    d = signed_boundary_distance(pt['x'], pt['y'])
    return d > 0 if category == 'A' else d < 0


def point_in_category_ellipse(pt: Dict[str, float], category: str, geometry) -> bool:
    center = geometry['center_a'] if category == 'A' else geometry['center_b']
    rel = (pt['x'] - center['x'], pt['y'] - center['y'])
    major_coord = dot(rel, T_MAJOR)
    minor_coord = dot(rel, N_MINOR)
    q = ((major_coord * major_coord) / (geometry['half_major'] * geometry['half_major'])
         + (minor_coord * minor_coord) / (geometry['half_minor'] * geometry['half_minor']))
    return q <= 1.0 + 1e-9


def point_in_category(pt: Dict[str, float], category: str, geometry) -> bool:
    return in_bounds(pt['x'], pt['y']) and point_on_category_side(pt, category) and point_in_category_ellipse(pt, category, geometry)


def sample_point_in_category(category: str, geometry, rng: random.Random) -> Dict[str, float]:
    center = geometry['center_a'] if category == 'A' else geometry['center_b']
    for _ in range(500):
        r = math.sqrt(rng.random())
        theta = rng.uniform(0.0, 2.0 * math.pi)
        major_coord = geometry['half_major'] * r * math.cos(theta)
        minor_coord = geometry['half_minor'] * r * math.sin(theta)
        pt = {
            'x': center['x'] + T_MAJOR[0] * major_coord + N_MINOR[0] * minor_coord,
            'y': center['y'] + T_MAJOR[1] * major_coord + N_MINOR[1] * minor_coord,
        }
        if point_in_category(pt, category, geometry):
            return pt
    return {'x': center['x'], 'y': center['y']}


def sample_within_pair(category: str, distance: float, geometry, rng: random.Random):
    for _ in range(500):
        center = sample_point_in_category(category, geometry, rng)
        p1 = shift_point(center, T_MAJOR, distance * 0.5)
        p2 = shift_point(center, T_MAJOR, -distance * 0.5)
        if point_in_category(p1, category, geometry) and point_in_category(p2, category, geometry):
            return {'ref': p1, 'cmp': p2}
    center = sample_point_in_category(category, geometry, rng)
    return {'ref': center, 'cmp': shift_point(center, T_MAJOR, 0.01)}


def sample_between_pair(distance: float, geometry, rng: random.Random):
    for _ in range(500):
        t = rng.uniform(0.15, 0.85)
        mid = {'x': X_MIN + (X_MAX - X_MIN) * t, 'y': Y_MIN + (Y_MAX - Y_MIN) * t}
        p_a = shift_point(mid, N_MINOR, distance * 0.5)
        p_b = shift_point(mid, N_MINOR, -distance * 0.5)
        if point_in_category(p_a, 'A', geometry) and point_in_category(p_b, 'B', geometry):
            return {'ref': p_a, 'cmp': p_b}
    return {
        'ref': shift_point({'x': SPACE_CENTER[0], 'y': SPACE_CENTER[1]}, N_MINOR, 0.5),
        'cmp': shift_point({'x': SPACE_CENTER[0], 'y': SPACE_CENTER[1]}, N_MINOR, -0.5),
    }


def make_cp_cells(dist_small: float, dist_large: float):
    dists = [
        {'level': 'near', 'distance': dist_small},
        {'level': 'far', 'distance': dist_large},
    ]
    cells = []
    for family in ['within_A', 'within_B', 'between_AB']:
        for d in dists:
            cells.append({'family': family, 'distance_level': d['level'], 'distance': float(d['distance'])})
    return cells


def cell_to_legacy_fields(cell):
    if cell['family'] == 'within_A':
        return {'pair_type': 'within', 'side': 1}
    if cell['family'] == 'within_B':
        return {'pair_type': 'within', 'side': -1}
    return {'pair_type': 'across', 'side': 0}


def make_cp_trials(rng: random.Random):
    if (CP_PRACTICE_FAR_N + CP_PRACTICE_MODERATE_N) != CP_PRACTICE_N:
        raise ValueError('Practice split constants must sum to CP_PRACTICE_N.')

    cells = make_cp_cells(CP_DIST_SMALL, CP_DIST_LARGE)

    practice = []
    families = ['within_A', 'within_B', 'between_AB']
    practice_specs = [
        ('far', float(CP_DIST_LARGE), CP_PRACTICE_FAR_N),
        ('moderate', float(CP_PRACTICE_MODERATE_DIST), CP_PRACTICE_MODERATE_N),
    ]
    for level, dist, n_trials in practice_specs:
        base = n_trials // len(families)
        rem = n_trials % len(families)
        fam_order = list(families)
        rng.shuffle(fam_order)
        for i, family in enumerate(fam_order):
            n_here = base + (1 if i < rem else 0)
            for _ in range(n_here):
                cell = {'family': family, 'distance_level': level, 'distance': dist}
                practice.append({
                    'trial_type': 'practice',
                    'cell': dict(cell),
                    'condition_id': f"practice_{cell['family']}_{cell['distance_level']}_{cell['distance']:.3f}",
                })
    rng.shuffle(practice)

    mains = []
    for cell in cells:
        for _ in range(CP_MAIN_REPS_PER_CELL):
            mains.append({
                'trial_type': 'main',
                'cell': dict(cell),
                'condition_id': f"{cell['family']}_{cell['distance_level']}_{cell['distance']:.3f}",
            })
    rng.shuffle(mains)

    if len(practice) != CP_PRACTICE_N:
        raise ValueError(f'Practice trial count mismatch: expected {CP_PRACTICE_N}, got {len(practice)}')
    return practice, mains


def build_cp_runtime(trial_def, geometry, rng: random.Random):
    cell = trial_def['cell']
    if cell['family'] == 'within_A':
        pair = sample_within_pair('A', cell['distance'], geometry, rng)
    elif cell['family'] == 'within_B':
        pair = sample_within_pair('B', cell['distance'], geometry, rng)
    else:
        pair = sample_between_pair(cell['distance'], geometry, rng)

    diff_interval = 1 if rng.random() < 0.5 else 2
    flip_order = rng.random() < 0.5

    same_pair = {'a': pair['ref'], 'b': pair['ref']}
    diff_pair = {'a': pair['cmp'], 'b': pair['ref']} if flip_order else {'a': pair['ref'], 'b': pair['cmp']}

    int1 = diff_pair if diff_interval == 1 else same_pair
    int2 = diff_pair if diff_interval == 2 else same_pair

    legacy = cell_to_legacy_fields(cell)

    return {
        'trial_type': trial_def['trial_type'],
        'condition_id': trial_def['condition_id'],
        'cp_family': cell['family'],
        'cp_distance_level': cell['distance_level'],
        'distance': cell['distance'],
        'pair_type': legacy['pair_type'],
        'band': cell['distance_level'],
        'side': legacy['side'],
        'diff_interval': diff_interval,
        'int1a': int1['a'],
        'int1b': int1['b'],
        'int2a': int2['a'],
        'int2b': int2['b'],
    }


def cp_condition_trigger(runtime) -> int:
    family = runtime['cp_family']
    level = runtime['cp_distance_level']
    if family == 'within_A' and level == 'near':
        return TRIG['CP_STIM_WITHIN_A_NEAR']
    if family == 'within_A' and level == 'far':
        return TRIG['CP_STIM_WITHIN_A_FAR']
    if family == 'within_B' and level == 'near':
        return TRIG['CP_STIM_WITHIN_B_NEAR']
    if family == 'within_B' and level == 'far':
        return TRIG['CP_STIM_WITHIN_B_FAR']
    if family == 'between_AB' and level == 'near':
        return TRIG['CP_STIM_ACROSS_NEAR']
    return TRIG['CP_STIM_ACROSS_FAR']


def make_rsa_pool_centered_grid(pool_seed: str) -> List[Dict[str, float]]:
    # Deterministic 7x7 grid with compressed x-range for visible lower-SF bound.
    _ = pool_seed
    if RSA_POOL_GRID_N <= 1:
        raise ValueError('RSA_POOL_GRID_N must be > 1')
    step_x = (RSA_POOL_X_MAX - RSA_POOL_X_MIN) / (RSA_POOL_GRID_N - 1)
    step_y = (RSA_POOL_Y_MAX - RSA_POOL_Y_MIN) / (RSA_POOL_GRID_N - 1)
    xs = [RSA_POOL_X_MIN + i * step_x for i in range(RSA_POOL_GRID_N)]
    ys = [RSA_POOL_Y_MIN + j * step_y for j in range(RSA_POOL_GRID_N)]
    pool = []
    item_id = 0
    for y in ys:
        for x in xs:
            pool.append({'item_id': item_id, 'x': x, 'y': y})
            item_id += 1
    return pool


def _assign_extra_blocks_exact(n_items: int, n_blocks: int, extras_per_item: int, extras_targets: List[int],
                               rng: random.Random) -> List[List[int]]:
    # Greedy with retries: enforce exact per-block counts and <=1 extra per item per block.
    if len(extras_targets) != n_blocks:
        raise ValueError('extras_targets length mismatch')
    for _ in range(200):
        remaining = list(extras_targets)
        assignment = [[] for _ in range(n_items)]
        item_order = list(range(n_items))
        rng.shuffle(item_order)
        ok = True

        for item in item_order:
            chosen = []
            for _k in range(extras_per_item):
                candidates = [b for b in range(n_blocks) if remaining[b] > 0 and b not in chosen]
                if not candidates:
                    ok = False
                    break
                max_remaining = max(remaining[b] for b in candidates)
                top = [b for b in candidates if remaining[b] == max_remaining]
                b = rng.choice(top)
                chosen.append(b)
                remaining[b] -= 1
            if not ok:
                break
            assignment[item] = chosen

        if ok and all(v == 0 for v in remaining):
            return assignment

    raise RuntimeError('Failed to build exact RSA extras-by-block assignment.')


def _reduce_adjacent_item_repeats(item_ids: List[int]):
    for i in range(1, len(item_ids)):
        if item_ids[i] != item_ids[i - 1]:
            continue
        swap_j = None
        for j in range(i + 1, len(item_ids)):
            if item_ids[j] != item_ids[i - 1] and (j == len(item_ids) - 1 or item_ids[j] != item_ids[j + 1]):
                swap_j = j
                break
        if swap_j is None:
            for j in range(i + 1, len(item_ids)):
                if item_ids[j] != item_ids[i - 1]:
                    swap_j = j
                    break
        if swap_j is not None:
            item_ids[i], item_ids[swap_j] = item_ids[swap_j], item_ids[i]


def make_rsa_schedule(pool: List[Dict[str, float]], schedule_seed: str) -> List[List[int]]:
    if len(pool) != RSA_POOL_SIZE:
        raise ValueError('RSA pool size mismatch.')
    if RSA_POOL_SIZE * RSA_REPEATS_PER_ITEM != RSA_TOTAL_TRIALS:
        raise ValueError('RSA repeat config mismatch.')

    rng = random.Random(schedule_seed)

    base_per_block = RSA_REPEATS_PER_ITEM // RSA_BLOCKS
    extras_per_item = RSA_REPEATS_PER_ITEM % RSA_BLOCKS
    total_extras = RSA_POOL_SIZE * extras_per_item
    extras_per_block_base = total_extras // RSA_BLOCKS
    extras_per_block_rem = total_extras % RSA_BLOCKS
    extras_targets = [extras_per_block_base + (1 if b < extras_per_block_rem else 0) for b in range(RSA_BLOCKS)]
    rng.shuffle(extras_targets)

    extras_assignment = _assign_extra_blocks_exact(
        n_items=RSA_POOL_SIZE,
        n_blocks=RSA_BLOCKS,
        extras_per_item=extras_per_item,
        extras_targets=extras_targets,
        rng=rng,
    )

    blocks = [[] for _ in range(RSA_BLOCKS)]
    for item_id in range(RSA_POOL_SIZE):
        extra_set = set(extras_assignment[item_id])
        for b in range(RSA_BLOCKS):
            n_here = base_per_block + (1 if b in extra_set else 0)
            blocks[b].extend([item_id] * n_here)

    block_sizes = [RSA_TOTAL_TRIALS // RSA_BLOCKS + (1 if b < (RSA_TOTAL_TRIALS % RSA_BLOCKS) else 0) for b in range(RSA_BLOCKS)]
    block_sizes.sort(reverse=True)
    actual_sizes = sorted([len(block) for block in blocks], reverse=True)
    if actual_sizes != block_sizes:
        raise ValueError(f'RSA block size mismatch: expected multiset {block_sizes}, got {actual_sizes}')

    for b in range(RSA_BLOCKS):
        rng.shuffle(blocks[b])
        _reduce_adjacent_item_repeats(blocks[b])

    return blocks


# --------------------------- Logging helpers -------------------------------------
FIELDNAMES = [
    'ts_iso', 'event',
    'participant', 'session', 'day', 'mode', 'design', 'seed',
    'trial_type', 'trial_index', 'cp_main_index', 'cp_practice_index', 'block_id',
    'condition_id', 'pair_type', 'band', 'side', 'cp_family', 'cp_distance_level', 'distance',
    'key', 'rt_ms', 'correct', 'diff_interval',
    'i1a_x', 'i1a_y', 'i1b_x', 'i1b_y', 'i2a_x', 'i2a_y', 'i2b_x', 'i2b_y',
    'interval1_changed', 'interval2_changed',
    'signed_dist_i1a', 'signed_dist_i1b', 'signed_dist_i2a', 'signed_dist_i2b',
    'rsa_point_index', 'rsa_chunk_index', 'cp_post_rsa_trial_index',
    'rsa_trial_index_global', 'rsa_trial_index_block',
    'rsa_block_index', 'rsa_item_id', 'rsa_x', 'rsa_y', 'rsa_sf', 'rsa_ori_deg',
    'rsa_pool_seed', 'rsa_schedule_seed',
    'trigger_code', 'trigger_label', 'trigger_source',
    'eeg_enabled', 'port_address',
    'cat_axis_gap', 'cat_major_axis_frac', 'cat_minor_axis_len',
    'cp_dist_small', 'cp_dist_large',
]


def write_row(writer, fhandle, base_meta, payload):
    row = {k: '' for k in FIELDNAMES}
    row.update(base_meta)
    row.update(payload)
    writer.writerow(row)
    fhandle.flush()


def log_trigger_event(writer, fhandle, base_meta, event_name, trig_code, payload=None):
    extra = {} if payload is None else dict(payload)
    write_row(
        writer,
        fhandle,
        base_meta,
        {
            'ts_iso': now_iso(),
            'event': event_name,
            'trigger_code': trig_code,
            'trigger_label': TRIG_NAME_BY_CODE.get(trig_code, ''),
            'trigger_source': 'both' if base_meta['eeg_enabled'] == 1 else 'csv',
            **extra,
        },
    )


# --------------------------- Main experiment -------------------------------------
if __name__ == '__main__':

    # --------------------------- Display / geometry -----------------------------
    pixels_per_inch = 227 / 2
    px_per_cm = pixels_per_inch / 2.54
    size_cm = 5
    size_px = int(size_cm * px_per_cm)

    win = visual.Window(size=(1920, 1080),
                        fullscr=True,
                        units='pix',
                        color=(0.494, 0.494, 0.494),
                        colorSpace='rgb',
                        winType='pyglet',
                        useRetina=True,
                        waitBlanking=True)
    win.mouseVisible = False

    # Text stimuli
    msg_text = visual.TextStim(win, text='', color='white', height=32, wrapWidth=1600)
    prompt_text = visual.TextStim(win, text='', color='white', height=30, wrapWidth=1600, pos=(0, 0))

    # Fixation
    fix_h = visual.ShapeStim(win, vertices=[(-20, 0), (20, 0)], lineWidth=6, lineColor='white', closeShape=False)
    fix_v = visual.ShapeStim(win, vertices=[(0, -20), (0, 20)], lineWidth=6, lineColor='white', closeShape=False)

    # Main grating (CP + RSA)
    grating = visual.GratingStim(win,
                                 tex='sin',
                                 mask='circle',
                                 interpolate=True,
                                 size=(size_px, size_px),
                                 units='pix',
                                 sf=0.02,
                                 ori=0.0,
                                 phase=0.0,
                                 pos=(0, 0))

    default_clock = core.Clock()
    trial_clock = core.Clock()

    eeg = EEGPort(win)

    # --------------------------- Participant/session entry ----------------------
    pid_input = ''
    pid_error = ''
    while True:
        msg_text.text = (
            f'Enter {PID_DIGITS}-digit Participant ID\n\n'
            f'ID: {pid_input or "___"}\n\n'
            'Press ENTER to continue, BACKSPACE to edit, ESC to quit.\n'
            f'{pid_error}'
        )
        msg_text.draw()
        win.flip()

        keys = event.getKeys()
        for k in keys:
            if k == 'escape':
                eeg.close()
                win.close()
                core.quit()
                sys.exit()
            if k == 'backspace':
                pid_input = pid_input[:-1]
                pid_error = ''
                continue
            if k in {'return', 'num_enter'}:
                if len(pid_input) != PID_DIGITS:
                    pid_error = f'\nInvalid ID format. Enter exactly {PID_DIGITS} digits.'
                    continue
                if pid_input not in ALLOWED_SUBJECT_IDS:
                    pid_error = '\nThis Participant ID is not enrolled for this study.'
                    continue
                participant = pid_input
                break

            digit = None
            if re.fullmatch(r'[0-9]', k):
                digit = k
            else:
                m = re.fullmatch(r'num_([0-9])', k)
                if m:
                    digit = m.group(1)
            if digit is not None and len(pid_input) < PID_DIGITS:
                pid_input += digit
                pid_error = ''
        else:
            continue
        break

    # Session number
    sess_input = ''
    sess_error = ''
    while True:
        msg_text.text = (
            'Enter 3-digit Session Number\n\n'
            f'Session: {sess_input or "___"}\n\n'
            'Press ENTER to continue, BACKSPACE to edit, ESC to quit.\n'
            f'{sess_error}'
        )
        msg_text.draw()
        win.flip()

        keys = event.getKeys()
        for k in keys:
            if k == 'escape':
                eeg.close()
                win.close()
                core.quit()
                sys.exit()
            if k == 'backspace':
                sess_input = sess_input[:-1]
                sess_error = ''
                continue
            if k in {'return', 'num_enter'}:
                if len(sess_input) != 3:
                    sess_error = '\nInvalid session format. Enter exactly 3 digits.'
                    continue
                session = sess_input
                break

            digit = None
            if re.fullmatch(r'[0-9]', k):
                digit = k
            else:
                m = re.fullmatch(r'num_([0-9])', k)
                if m:
                    digit = m.group(1)
            if digit is not None and len(sess_input) < 3:
                sess_input += digit
                sess_error = ''
        else:
            continue
        break

    # Day label (baseline/post)
    day = 'baseline'
    day_selected = False
    while not day_selected:
        msg_text.text = (
            'Select Day:\n\n'
            '1 = baseline\n'
            '2 = post1\n'
            '3 = post2\n\n'
            'Press 1/2/3 to continue, ESC to quit.'
        )
        msg_text.draw()
        win.flip()

        keys = event.getKeys()
        for k in keys:
            if k == 'escape':
                eeg.close()
                win.close()
                core.quit()
                sys.exit()
            if k in {'1', 'num_1'}:
                day = 'baseline'
                day_selected = True
                break
            if k in {'2', 'num_2'}:
                day = 'post1'
                day_selected = True
                break
            if k in {'3', 'num_3'}:
                day = 'post2'
                day_selected = True
                break

    seed = f'{participant}_{session}_{MODE}_{day}'
    rng = random.Random(seed)
    rsa_schedule_seed = f'{seed}_rsa_schedule'
    geometry = create_category_geometry()
    rsa_pool = make_rsa_pool_centered_grid(RSA_POOL_SEED)
    rsa_blocks = make_rsa_schedule(rsa_pool, rsa_schedule_seed)
    rsa_pool_by_id = {int(item['item_id']): item for item in rsa_pool}

    # Safety checks for fixed-pool RSA design.
    assert len(rsa_pool) == RSA_POOL_SIZE
    assert len(rsa_blocks) == RSA_BLOCKS
    flat_rsa = [item_id for block in rsa_blocks for item_id in block]
    assert len(flat_rsa) == RSA_TOTAL_TRIALS
    repeats_by_item = {item_id: 0 for item_id in range(RSA_POOL_SIZE)}
    for item_id in flat_rsa:
        repeats_by_item[int(item_id)] += 1
    assert all(v == RSA_REPEATS_PER_ITEM for v in repeats_by_item.values())

    # --------------------------- Data file setup --------------------------------
    dir_data = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data'))
    os.makedirs(dir_data, exist_ok=True)

    timestamp = datetime.now().strftime('%Y-%m-%d_%Hh%M.%S.%f')[:-3]
    file_name = f'{participant}_{MODE}_{DESIGN}_{timestamp}.csv'
    full_path = os.path.join(dir_data, file_name)

    base_meta = {
        'participant': participant,
        'session': session,
        'day': day,
        'mode': MODE,
        'design': DESIGN,
        'seed': seed,
        'eeg_enabled': int(bool(eeg.enabled)),
        'port_address': EEG_PORT_ADDRESS if eeg.enabled else '',
        'cat_axis_gap': CAT_AXIS_GAP,
        'cat_major_axis_frac': CAT_MAJOR_AXIS_FRAC,
        'cat_minor_axis_len': CAT_MINOR_AXIS_LEN,
        'cp_dist_small': CP_DIST_SMALL,
        'cp_dist_large': CP_DIST_LARGE,
        'rsa_pool_seed': RSA_POOL_SEED,
        'rsa_schedule_seed': rsa_schedule_seed,
    }

    fhandle = open(full_path, 'w', newline='', encoding='utf-8')
    writer = csv.DictWriter(fhandle, fieldnames=FIELDNAMES)
    writer.writeheader()
    fhandle.flush()
    runtime_state = {'rsa_trial_global': 0}

    # --------------------------- Helper drawers ---------------------------------
    def draw_message(text: str):
        msg_text.text = text
        msg_text.draw()

    def show_message_wait_space(text: str,
                                trigger_onset=None,
                                trigger_confirm=None,
                                event_onset='screen_onset',
                                event_confirm='screen_confirm',
                                payload=None):
        payload = {} if payload is None else dict(payload)
        draw_message(text)
        if trigger_onset is not None:
            eeg.flip_pulse(trigger_onset, global_clock=default_clock)
        win.flip()
        if trigger_onset is not None:
            log_trigger_event(writer, fhandle, base_meta, event_onset, trigger_onset, payload)

        while True:
            eeg.update(default_clock)
            keys = event.getKeys(keyList=['space', 'escape'])
            if 'escape' in keys:
                return False
            if 'space' in keys:
                if trigger_confirm is not None:
                    eeg.pulse_now(trigger_confirm, global_clock=default_clock)
                    log_trigger_event(writer, fhandle, base_meta, event_confirm, trigger_confirm, payload)
                return True
            draw_message(text)
            win.flip()

    def run_rsa_chunk(point_idx: int, chunk_idx: int, block_idx: int, start_code: int, end_code: int):
        nonlocal_runtime = runtime_state
        block_trials = rsa_blocks[block_idx - 1]

        # Flip-locked chunk onset
        fix_h.draw()
        fix_v.draw()
        grating.phase = 0.0
        grating.ori = 0.0
        grating.sf = 0.02
        grating.draw()
        eeg.flip_pulse(start_code, global_clock=default_clock)
        win.flip()
        log_trigger_event(
            writer,
            fhandle,
            base_meta,
            f'rsa_chunk_start',
            start_code,
            {
                'rsa_point_index': point_idx,
                'rsa_chunk_index': chunk_idx,
                'rsa_block_index': block_idx,
                'event': 'rsa_chunk_start',
            },
        )

        for i_block, item_id in enumerate(block_trials, start=1):
            item = rsa_pool_by_id[int(item_id)]
            sf, ori = to_stim_params(item['x'], item['y'])
            grating.sf = sf
            grating.ori = ori
            grating.phase = 0.0

            trial_clock = core.Clock()
            while trial_clock.getTime() < RSA_SOA_SEC:
                eeg.update(default_clock)
                if 'escape' in event.getKeys(keyList=['escape']):
                    return False
                fix_h.draw()
                fix_v.draw()
                grating.draw()
                win.flip()

            nonlocal_runtime['rsa_trial_global'] += 1
            write_row(
                writer,
                fhandle,
                base_meta,
                {
                    'ts_iso': now_iso(),
                    'event': 'rsa_trial',
                    'trial_type': 'rsa',
                    'trial_index': nonlocal_runtime['rsa_trial_global'],
                    'rsa_point_index': point_idx,
                    'rsa_chunk_index': chunk_idx,
                    'rsa_block_index': block_idx,
                    'rsa_trial_index_global': nonlocal_runtime['rsa_trial_global'],
                    'rsa_trial_index_block': i_block,
                    'rsa_item_id': item_id,
                    'rsa_x': item['x'],
                    'rsa_y': item['y'],
                    'rsa_sf': sf,
                    'rsa_ori_deg': ori,
                },
            )

        eeg.pulse_now(end_code, global_clock=default_clock)
        log_trigger_event(
            writer,
            fhandle,
            base_meta,
            f'rsa_chunk_end',
            end_code,
            {
                'rsa_point_index': point_idx,
                'rsa_chunk_index': chunk_idx,
                'rsa_block_index': block_idx,
                'event': 'rsa_chunk_end',
            },
        )
        return True

    def run_rsa_point(point_idx: int):
        block_1 = ((point_idx - 1) * RSA_CHUNKS_PER_POINT) + 1
        block_2 = block_1 + 1

        ok = show_message_wait_space(
            'You will now see flashing stimuli for 1 minute.\n'
            'Please stay relaxed, keep your eyes on the center of the screen, and minimize movement.\n'
            'This may feel repetitive or boring, but please keep looking at the centre and try to stay awake!\n\n'
            'Press SPACE to start.',
            event_onset='rsa_instr_onset',
            payload={'rsa_point_index': point_idx, 'event': 'rsa_instruction'},
        )
        if not ok:
            return False

        ok = run_rsa_chunk(point_idx, 1, block_1, TRIG['RSA_CHUNK1_START'], TRIG['RSA_CHUNK1_END'])
        if not ok:
            return False

        ok = show_message_wait_space(
            'Another 1-minute block is about to start.\n'
            'Feel free to wriggle, blink, and get comfortable before you begin.\n\n'
            'Press SPACE when you are ready.',
            trigger_onset=TRIG['RSA_READY_ONSET'],
            event_onset='rsa_ready_onset',
            event_confirm='rsa_ready_confirm',
            payload={'rsa_point_index': point_idx, 'event': 'rsa_ready'},
        )
        if not ok:
            return False

        ok = run_rsa_chunk(point_idx, 2, block_2, TRIG['RSA_CHUNK2_START'], TRIG['RSA_CHUNK2_END'])
        if not ok:
            return False

        write_row(
            writer,
            fhandle,
            base_meta,
            {
                'ts_iso': now_iso(),
                'event': 'rsa_point_end',
                'rsa_point_index': point_idx,
                'rsa_block_index': f'{block_1},{block_2}',
            },
        )
        return True

    def stage_cp_stim(pt):
        sf, ori = to_stim_params(pt['x'], pt['y'])
        grating.sf = sf
        grating.ori = ori
        grating.phase = 0.0

    def run_phase(duration_sec: float,
                  draw_kind: str,
                  trig_code=None,
                  trig_event='cp_phase'):
        clock = core.Clock()
        first = True
        while clock.getTime() < duration_sec:
            eeg.update(default_clock)
            if 'escape' in event.getKeys(keyList=['escape']):
                return False

            if draw_kind == 'fix':
                fix_h.draw()
                fix_v.draw()
            elif draw_kind == 'stim':
                grating.draw()
            elif draw_kind == 'blank':
                pass

            if first and trig_code is not None:
                eeg.flip_pulse(trig_code, global_clock=default_clock)
                win.flip()
                log_trigger_event(writer, fhandle, base_meta, trig_event, trig_code)
                first = False
            else:
                win.flip()
                first = False
        return True

    def run_cp_trial(runtime, trial_index: int, cp_main_index, cp_practice_index, block_id: int, post_rsa_idx):
        # Optional marker for first trial after RSA
        if post_rsa_idx == 0:
            eeg.pulse_now(TRIG['CP_TRIAL_POST_RSA_FLAG'], global_clock=default_clock)
            log_trigger_event(
                writer,
                fhandle,
                base_meta,
                'cp_trial_post_rsa_flag',
                TRIG['CP_TRIAL_POST_RSA_FLAG'],
                {'cp_main_index': cp_main_index if cp_main_index is not None else '', 'cp_post_rsa_trial_index': 0},
            )

        # ITI with jitter
        iti = ITI_SEC + rng.uniform(ITI_JITTER_SEC[0], ITI_JITTER_SEC[1])
        ok = run_phase(iti, 'fix', trig_code=TRIG['CP_ITI_ONSET'], trig_event='cp_iti_onset')
        if not ok:
            return False, None

        # Interval 1A
        stage_cp_stim(runtime['int1a'])
        ok = run_phase(INTERVAL_SEC, 'stim', trig_code=TRIG['CP_INTERVAL1_ONSET'], trig_event='cp_interval1_onset')
        if not ok:
            return False, None
        if runtime['trial_type'] == 'main':
            cond_code = cp_condition_trigger(runtime)
            eeg.pulse_now(cond_code, global_clock=default_clock)
            log_trigger_event(writer, fhandle, base_meta, 'cp_condition_interval1', cond_code)

        # Interval 1B
        ok = run_phase(PAIR_GAP_SEC, 'blank')
        if not ok:
            return False, None
        stage_cp_stim(runtime['int1b'])
        ok = run_phase(INTERVAL_SEC, 'stim')
        if not ok:
            return False, None

        # ISI
        ok = run_phase(ISI_SEC, 'fix')
        if not ok:
            return False, None

        # Interval 2A
        stage_cp_stim(runtime['int2a'])
        ok = run_phase(INTERVAL_SEC, 'stim', trig_code=TRIG['CP_INTERVAL2_ONSET'], trig_event='cp_interval2_onset')
        if not ok:
            return False, None

        # Interval 2B
        ok = run_phase(PAIR_GAP_SEC, 'blank')
        if not ok:
            return False, None
        stage_cp_stim(runtime['int2b'])
        ok = run_phase(INTERVAL_SEC, 'stim')
        if not ok:
            return False, None

        # Response
        prompt_text.text = 'Which interval had the different pair?\n 1 = Interval 1, 2 = Interval 2'
        resp_clock = core.Clock()

        prompt_text.draw()
        eeg.flip_pulse(TRIG['CP_RESPONSE_PROMPT_ONSET'], global_clock=default_clock)
        win.flip()
        log_trigger_event(writer, fhandle, base_meta, 'cp_response_prompt_onset', TRIG['CP_RESPONSE_PROMPT_ONSET'])

        key_name = 'none'
        rt_ms = ''
        correct = 0

        while resp_clock.getTime() < RESP_WINDOW_SEC:
            eeg.update(default_clock)
            keys = event.getKeys(keyList=['1', '2', 'num_1', 'num_2', 'escape'])
            if 'escape' in keys:
                return False, None
            if keys:
                key_name = keys[-1]
                picked = key_to_interval(key_name)
                rt_ms = resp_clock.getTime() * 1000.0
                correct = 1 if picked == runtime['diff_interval'] else 0
                if picked == 1:
                    eeg.pulse_now(TRIG['CP_RESP_1'], global_clock=default_clock)
                    log_trigger_event(writer, fhandle, base_meta, 'cp_resp_1', TRIG['CP_RESP_1'])
                elif picked == 2:
                    eeg.pulse_now(TRIG['CP_RESP_2'], global_clock=default_clock)
                    log_trigger_event(writer, fhandle, base_meta, 'cp_resp_2', TRIG['CP_RESP_2'])
                break
            prompt_text.draw()
            win.flip()

        if key_name == 'none':
            eeg.pulse_now(TRIG['CP_RESP_TIMEOUT'], global_clock=default_clock)
            log_trigger_event(writer, fhandle, base_meta, 'cp_resp_timeout', TRIG['CP_RESP_TIMEOUT'])

        if runtime['trial_type'] == 'practice':
            if key_name == 'none':
                prompt_text.text = 'Too slow'
            elif correct == 1:
                prompt_text.text = 'Correct'
            else:
                prompt_text.text = 'Incorrect'
            fb_clock = core.Clock()
            while fb_clock.getTime() < PRACTICE_FEEDBACK_SEC:
                eeg.update(default_clock)
                if 'escape' in event.getKeys(keyList=['escape']):
                    return False, None
                prompt_text.draw()
                win.flip()

        # Trial end trigger and row
        eeg.pulse_now(TRIG['CP_TRIAL_END'], global_clock=default_clock)
        log_trigger_event(writer, fhandle, base_meta, 'cp_trial_end', TRIG['CP_TRIAL_END'])

        write_row(
            writer,
            fhandle,
            base_meta,
            {
                'ts_iso': now_iso(),
                'event': 'cp_trial',
                'trial_type': runtime['trial_type'],
                'trial_index': trial_index,
                'cp_main_index': cp_main_index if cp_main_index is not None else '',
                'cp_practice_index': cp_practice_index if cp_practice_index is not None else '',
                'block_id': block_id,
                'condition_id': runtime['condition_id'],
                'pair_type': runtime['pair_type'],
                'band': runtime['band'],
                'side': runtime['side'],
                'cp_family': runtime['cp_family'],
                'cp_distance_level': runtime['cp_distance_level'],
                'distance': runtime['distance'],
                'key': key_name,
                'rt_ms': rt_ms,
                'correct': correct,
                'diff_interval': runtime['diff_interval'],
                'i1a_x': runtime['int1a']['x'],
                'i1a_y': runtime['int1a']['y'],
                'i1b_x': runtime['int1b']['x'],
                'i1b_y': runtime['int1b']['y'],
                'i2a_x': runtime['int2a']['x'],
                'i2a_y': runtime['int2a']['y'],
                'i2b_x': runtime['int2b']['x'],
                'i2b_y': runtime['int2b']['y'],
                'interval1_changed': 1 if has_visible_difference(runtime['int1a'], runtime['int1b']) else 0,
                'interval2_changed': 1 if has_visible_difference(runtime['int2a'], runtime['int2b']) else 0,
                'signed_dist_i1a': signed_boundary_distance(runtime['int1a']['x'], runtime['int1a']['y']),
                'signed_dist_i1b': signed_boundary_distance(runtime['int1b']['x'], runtime['int1b']['y']),
                'signed_dist_i2a': signed_boundary_distance(runtime['int2a']['x'], runtime['int2a']['y']),
                'signed_dist_i2b': signed_boundary_distance(runtime['int2b']['x'], runtime['int2b']['y']),
                'cp_post_rsa_trial_index': post_rsa_idx if post_rsa_idx is not None else '',
            },
        )

        return True, correct

    # --------------------------- Start prompt -----------------------------------
    draw_message('Experiment ready.\n\nPress SPACE to begin.')
    win.flip()
    while True:
        keys = event.getKeys(keyList=['space', 'escape'])
        if 'escape' in keys:
            eeg.close()
            fhandle.close()
            win.close()
            core.quit()
            sys.exit()
        if 'space' in keys:
            eeg.pulse_now(TRIG['EXP_START'], global_clock=default_clock)
            log_trigger_event(writer, fhandle, base_meta, 'exp_start', TRIG['EXP_START'])
            break
        core.wait(0.01)

    write_row(writer, fhandle, base_meta, {'ts_iso': now_iso(), 'event': 'meta_confirmed'})

    # --------------------------- Build CP schedules -----------------------------
    practice_trials, main_trials = make_cp_trials(rng)

    # --------------------------- RSA point 1 ------------------------------------
    if not run_rsa_point(point_idx=1):
        eeg.pulse_now(TRIG['EXP_END'], global_clock=default_clock)
        log_trigger_event(writer, fhandle, base_meta, 'exp_end_abort', TRIG['EXP_END'])
        eeg.close()
        fhandle.close()
        win.close()
        core.quit()
        sys.exit()

    # --------------------------- CP instruction ---------------------------------
    ok = show_message_wait_space(
        'You are about to start another task.\n'
        'In each trial two stimulus pairs will flash on the screen (Interval 1 and Interval 2).\n'
        'In one of these intervals, the two stimuli are different. In the other, they are the same.\n'
        'The stimuli can differ in bar thickness, angle, or both.\n'
        'Press 1 if the different pair was in interval 1.\n'
        'Press 2 if the different pair was in interval 2.\n'
        'Please keep your eyes centered on the middle of the stimulus.\n'
        'Try to respond as accurately as possible.\n'
        'You will begin with a short practice block.\n\n'
        'Press SPACE to start practice.',
        event_onset='cp_instr_onset',
        payload={'event': 'cp_instruction'},
    )
    if not ok:
        eeg.pulse_now(TRIG['EXP_END'], global_clock=default_clock)
        log_trigger_event(writer, fhandle, base_meta, 'exp_end_abort', TRIG['EXP_END'])
        eeg.close()
        fhandle.close()
        win.close()
        core.quit()
        sys.exit()

    # --------------------------- Practice block ---------------------------------
    eeg.pulse_now(TRIG['CP_PRACTICE_START'], global_clock=default_clock)
    log_trigger_event(writer, fhandle, base_meta, 'cp_practice_start', TRIG['CP_PRACTICE_START'])

    trial_counter = 0
    for p_idx, tdef in enumerate(practice_trials, start=1):
        runtime = build_cp_runtime(tdef, geometry, rng)
        ok, _ = run_cp_trial(runtime, trial_counter, None, p_idx, block_id=0, post_rsa_idx=None)
        if not ok:
            eeg.pulse_now(TRIG['EXP_END'], global_clock=default_clock)
            log_trigger_event(writer, fhandle, base_meta, 'exp_end_abort', TRIG['EXP_END'])
            eeg.close()
            fhandle.close()
            win.close()
            core.quit()
            sys.exit()
        trial_counter += 1

    eeg.pulse_now(TRIG['CP_PRACTICE_END'], global_clock=default_clock)
    log_trigger_event(writer, fhandle, base_meta, 'cp_practice_end', TRIG['CP_PRACTICE_END'])

    # --------------------------- CP main blocks ---------------------------------
    ok = show_message_wait_space(
        'Practice complete.\n'
        'Now the main task will begin.\n'
        'The main trials will be harder. Please try and respond as accurately as possible.\n'
        'Keep your eyes centered on the middle of the stimulus.\n'
        'Remember: 1 = interval 1, 2 = interval 2.\n\n'
        'Press SPACE to begin.'
    )
    if not ok:
        eeg.pulse_now(TRIG['EXP_END'], global_clock=default_clock)
        log_trigger_event(writer, fhandle, base_meta, 'exp_end_abort', TRIG['EXP_END'])
        eeg.close()
        fhandle.close()
        win.close()
        core.quit()
        sys.exit()

    main_index = 1
    block_id = 1
    rsa_point = 1
    post_rsa_first_trials = set(CP_MAIN_RSA_CHECKPOINTS)

    eeg.pulse_now(TRIG['CP_MAIN_BLOCK_START'], global_clock=default_clock)
    log_trigger_event(writer, fhandle, base_meta, 'cp_main_block_start', TRIG['CP_MAIN_BLOCK_START'], {'block_id': block_id})

    for tdef in main_trials:
        # RSA re-entry points for blocks 2..4
        if main_index in CP_MAIN_RSA_CHECKPOINTS[1:]:
            eeg.pulse_now(TRIG['CP_MAIN_BLOCK_END'], global_clock=default_clock)
            log_trigger_event(writer, fhandle, base_meta, 'cp_main_block_end', TRIG['CP_MAIN_BLOCK_END'], {'block_id': block_id})

            rsa_point += 1
            if not run_rsa_point(point_idx=rsa_point):
                eeg.pulse_now(TRIG['EXP_END'], global_clock=default_clock)
                log_trigger_event(writer, fhandle, base_meta, 'exp_end_abort', TRIG['EXP_END'])
                eeg.close()
                fhandle.close()
                win.close()
                core.quit()
                sys.exit()

            ok = show_message_wait_space(
                'You are about to continue the discrimination task.\n'
                'Feel free to wriggle and get comfortable before you begin.\n'
                'Keep your eyes centered on the middle of the stimulus.\n'
                'Remember: 1 = interval 1, 2 = interval 2.\n\n'
                'Press SPACE when ready.'
            )
            if not ok:
                eeg.pulse_now(TRIG['EXP_END'], global_clock=default_clock)
                log_trigger_event(writer, fhandle, base_meta, 'exp_end_abort', TRIG['EXP_END'])
                eeg.close()
                fhandle.close()
                win.close()
                core.quit()
                sys.exit()

            block_id += 1
            eeg.pulse_now(TRIG['CP_MAIN_BLOCK_START'], global_clock=default_clock)
            log_trigger_event(writer, fhandle, base_meta, 'cp_main_block_start', TRIG['CP_MAIN_BLOCK_START'], {'block_id': block_id})

        runtime = build_cp_runtime(tdef, geometry, rng)
        post_idx = 0 if main_index in post_rsa_first_trials else None

        ok, _ = run_cp_trial(runtime, trial_counter, main_index, None, block_id=block_id, post_rsa_idx=post_idx)
        if not ok:
            eeg.pulse_now(TRIG['EXP_END'], global_clock=default_clock)
            log_trigger_event(writer, fhandle, base_meta, 'exp_end_abort', TRIG['EXP_END'])
            eeg.close()
            fhandle.close()
            win.close()
            core.quit()
            sys.exit()

        trial_counter += 1
        main_index += 1

    eeg.pulse_now(TRIG['CP_MAIN_BLOCK_END'], global_clock=default_clock)
    log_trigger_event(writer, fhandle, base_meta, 'cp_main_block_end', TRIG['CP_MAIN_BLOCK_END'], {'block_id': block_id})

    # --------------------------- End screen -------------------------------------
    draw_message('Thank you for being awesome!\nPress SPACE to exit.')
    win.flip()
    while True:
        eeg.update(default_clock)
        keys = event.getKeys(keyList=['space', 'escape'])
        if keys:
            break
        core.wait(0.01)

    eeg.pulse_now(TRIG['EXP_END'], global_clock=default_clock)
    log_trigger_event(writer, fhandle, base_meta, 'exp_end', TRIG['EXP_END'])

    eeg.close()
    fhandle.close()
    win.close()
    core.quit()
