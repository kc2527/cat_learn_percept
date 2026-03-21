import { core, util, visual } from './psychojs/psychojs-2025.2.4.js';

const { PsychoJS } = core;
const { Scheduler } = util;

const EXP_NAME = 'cat_learn_percept';
const MODE_ACUITY = 'acuity_map_2afc';
const MODE_CP = 'cp_probe';
const DESIGN_PILOT = 'pilot';
const DESIGN_FULL = 'full';

const X_MIN = 0;
const X_MAX = 100;
const Y_MIN = 0;
const Y_MAX = 100;
const SF_OFFSET = 2.0;

const SQRT2 = Math.sqrt(2);
const SPACE_CENTER = { x: 50, y: 50 };
const SPACE_DIAG = Math.hypot(X_MAX - X_MIN, Y_MAX - Y_MIN);
const T_MAJOR = [1 / SQRT2, 1 / SQRT2];
const N_MINOR = [-1 / SQRT2, 1 / SQRT2];

const CP_PRACTICE_TRIALS_FULL = 24;

const PA_AXES_FULL = [
  { axisType: 'tangential', angleDeg: 45 },
  { axisType: 'normal', angleDeg: 135 },
];

const PROFILE_BY_MODE = {
  [MODE_ACUITY]: {
    [DESIGN_PILOT]: {
      timings: {
        itiSec: 0.4,
        intervalSec: 0.25,
        pairGapSec: 0.2,
        isiSec: 0.35,
        respWindowSec: null,
      },
      acuity: {
        points: null,
        axes: PA_AXES_FULL,
        deltaInit: 7,
        deltaMin: 1,
        deltaMax: 16,
        downGain: 0.85,
        upGain: 1.15,
        maxTrials: 6,
        maxReversals: 4,
      },
      blockBreaks: [],
      practiceTrials: 0,
    },
    [DESIGN_FULL]: {
      timings: {
        itiSec: 0.45,
        intervalSec: 0.22,
        pairGapSec: 0.15,
        isiSec: 0.35,
        respWindowSec: null,
      },
      acuity: {
        points: null, // generated from category geometry template
        axes: PA_AXES_FULL,
        deltaInit: 7,
        deltaMin: 1,
        deltaMax: 16,
        downGain: 0.85,
        upGain: 1.15,
        maxTrials: 8,
        maxReversals: 3,
      },
      blockBreaks: [150],
      practiceTrials: 0,
    },
  },
  [MODE_CP]: {
    [DESIGN_PILOT]: {
      timings: {
        itiSec: 0.4,
        intervalSec: 0.25,
        pairGapSec: 0.2,
        isiSec: 0.35,
        respWindowSec: null,
      },
      cp: {
        repsPerCondition: 20,
      },
      blockBreaks: [],
      practiceTrials: 0,
    },
    [DESIGN_FULL]: {
      timings: {
        itiSec: 0.5,
        intervalSec: 0.2,
        pairGapSec: 0.15,
        isiSec: 0.4,
        respWindowSec: 1.5,
        itiJitterSec: [0.0, 0.3],
      },
      cp: {
        repsPerCondition: 34,
      },
      blockBreaks: [100],
      practiceTrials: CP_PRACTICE_TRIALS_FULL,
    },
  },
};

let expInfo = {
  participant: '999',
  session: '001',
  day: 'unspecified',
  mode: MODE_ACUITY,
  design: DESIGN_PILOT,
  seed: '',
  debugPreview: false,
  catAxisGap: 20,
  catMajorAxisFrac: 0.8,
  catMinorAxisLen: 24,
  paAxisOffsets: [-18, 18],
  paOuterOffsets: [10, 18],
  cpDistSmall: 6,
  cpDistLarge: 12,
};

const psychoJS = new PsychoJS({ debug: true });
psychoJS.openWindow({
  fullscr: true,
  color: new util.Color([0.494, 0.494, 0.494]),
  units: 'height',
  waitBlanking: true,
});

const flowScheduler = new Scheduler(psychoJS);
psychoJS.schedule(flowScheduler);

flowScheduler.add(updateInfo);
flowScheduler.add(experimentInit);
flowScheduler.add(instructionsBegin());
flowScheduler.add(instructionsEachFrame());
flowScheduler.add(instructionsEnd());
flowScheduler.add(trialLoopInit);
for (let i = 0; i < 4000; i++) {
  flowScheduler.add(trialBegin(i));
  flowScheduler.add(trialEachFrame(i));
  flowScheduler.add(trialEnd(i));
}
flowScheduler.add(finalizeData);
flowScheduler.add(doneBegin());
flowScheduler.add(doneEachFrame());
flowScheduler.add(doneEnd());
flowScheduler.add(quitPsychoJS, 'Done', true);

psychoJS.start({ expName: EXP_NAME, expInfo, resources: [] });
psychoJS.experimentLogger.setLevel(core.Logger.ServerLevel.INFO);

let routineClock;
let infoText;
let promptText;
let intervalText;
let debugPreviewText;
let fixH;
let fixV;
let grating;
let previewGratings = [];
let previewLabels = [];
let previewValueTexts = [];
let previewOddHighlight;

const PREVIEW_LABELS = ['I1A', 'I1B', 'I2A', 'I2B'];
const PREVIEW_X_POSITIONS = [-0.48, -0.16, 0.16, 0.48];
const PREVIEW_Y = 0.02;
const PREVIEW_STIM_SIZE = 0.19;

let allTrials = [];
let blockComplete = false;
let trialDone = false;
let skipTrial = false;
let currentTrial = null;
let trialRuntime = null;
let phase = 'idle';

let staircases = [];
let staircasesById = new Map();

let profile = null;
let categoryGeometry = null;
let rng = null;
let breakCursor = 0;
let doneMainCount = 0;
let currentBlockId = 1;
let sawBreakThisTrial = false;
let jitteredItiSec = 0;

function nowISO() {
  return new Date().toISOString();
}

function clamp(v, lo, hi) {
  return Math.max(lo, Math.min(hi, v));
}

function fmt3(v) {
  const s = String(v);
  return /^\d+$/.test(s) ? s.padStart(3, '0') : s;
}

function parseBoolParam(raw) {
  if (raw == null) return false;
  const v = String(raw).trim().toLowerCase();
  return ['1', 'true', 'yes', 'y', 'on'].includes(v);
}

function parseFloatParam(raw, fallback) {
  const v = Number.parseFloat(raw);
  return Number.isFinite(v) ? v : fallback;
}

function parseFloatListParam(raw, fallback) {
  if (raw == null || String(raw).trim() === '') return fallback;
  const vals = String(raw)
    .split(',')
    .map((s) => Number.parseFloat(s.trim()))
    .filter(Number.isFinite);
  return vals.length > 0 ? vals : fallback;
}

function makeSeededRng(seedInput) {
  let state = 0;
  const src = String(seedInput || '');
  for (let i = 0; i < src.length; i++) {
    state = (state * 1664525 + src.charCodeAt(i) + 1013904223) >>> 0;
  }
  if (state === 0) state = 123456789;

  return {
    random() {
      state = (1664525 * state + 1013904223) >>> 0;
      return state / 4294967296;
    },
  };
}

function rand() {
  return rng ? rng.random() : Math.random();
}

function shuffle(arr) {
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1));
    const tmp = arr[i];
    arr[i] = arr[j];
    arr[j] = tmp;
  }
  return arr;
}

function randIn(lo, hi) {
  return lo + rand() * (hi - lo);
}

function inBounds(x, y) {
  return x >= X_MIN && x <= X_MAX && y >= Y_MIN && y <= Y_MAX;
}

function signedBoundaryDistance(x, y) {
  return (y - x) / SQRT2;
}

function dot(a, b) {
  return a[0] * b[0] + a[1] * b[1];
}

function shiftPoint(pt, dir, amount) {
  return { x: pt.x + dir[0] * amount, y: pt.y + dir[1] * amount };
}

function projectToSpaceFrame(x, y) {
  const rx = x - SPACE_CENTER.x;
  const ry = y - SPACE_CENTER.y;
  return {
    tCoord: dot([rx, ry], T_MAJOR),
    nCoord: dot([rx, ry], N_MINOR),
  };
}

function createCategoryGeometry() {
  const majorLen = clamp(expInfo.catMajorAxisFrac, 0.05, 0.95) * SPACE_DIAG;
  const halfMajor = majorLen * 0.5;
  const halfMinor = clamp(expInfo.catMinorAxisLen * 0.5, 1, SPACE_DIAG * 0.45);
  const halfGap = expInfo.catAxisGap * 0.5;
  return {
    majorLen,
    minorLen: halfMinor * 2,
    halfMajor,
    halfMinor,
    centerA: shiftPoint(SPACE_CENTER, N_MINOR, halfGap),
    centerB: shiftPoint(SPACE_CENTER, N_MINOR, -halfGap),
  };
}

function pointOnCategorySide(pt, category) {
  const d = signedBoundaryDistance(pt.x, pt.y);
  if (category === 'A') return d > 0;
  return d < 0;
}

function pointInCategoryEllipse(pt, category) {
  const center = category === 'A' ? categoryGeometry.centerA : categoryGeometry.centerB;
  const rel = [pt.x - center.x, pt.y - center.y];
  const majorCoord = dot(rel, T_MAJOR);
  const minorCoord = dot(rel, N_MINOR);
  const q = (majorCoord * majorCoord) / (categoryGeometry.halfMajor * categoryGeometry.halfMajor)
    + (minorCoord * minorCoord) / (categoryGeometry.halfMinor * categoryGeometry.halfMinor);
  return q <= 1.0 + 1e-9;
}

function pointInCategory(pt, category) {
  return inBounds(pt.x, pt.y) && pointOnCategorySide(pt, category) && pointInCategoryEllipse(pt, category);
}

function samplePointInCategory(category) {
  const center = category === 'A' ? categoryGeometry.centerA : categoryGeometry.centerB;
  for (let k = 0; k < 500; k++) {
    const r = Math.sqrt(rand());
    const theta = randIn(0, 2 * Math.PI);
    const majorCoord = categoryGeometry.halfMajor * r * Math.cos(theta);
    const minorCoord = categoryGeometry.halfMinor * r * Math.sin(theta);
    const pt = {
      x: center.x + T_MAJOR[0] * majorCoord + N_MINOR[0] * minorCoord,
      y: center.y + T_MAJOR[1] * majorCoord + N_MINOR[1] * minorCoord,
    };
    if (pointInCategory(pt, category)) return pt;
  }
  return { ...center };
}

function toStimParams(x, y) {
  return {
    sf: (x * 5) / 100 + SF_OFFSET,
    oriDeg: (y * 90) / 100,
  };
}

function hasVisibleDifference(a, b) {
  return Math.abs(a.x - b.x) + Math.abs(a.y - b.y) >= 0.75;
}

function unitFromAngleDeg(angleDeg) {
  const r = (angleDeg * Math.PI) / 180;
  return [Math.cos(r), Math.sin(r)];
}

function mkTrialBase(overrides = {}) {
  return {
    mode: expInfo.mode,
    design: expInfo.design,
    trialType: 'main',
    blockId: currentBlockId,
    conditionId: null,
    ...overrides,
  };
}

function makeAcuityPoints() {
  const points = [];
  const axisOffsets = expInfo.paAxisOffsets.slice(0, 2);
  const outerOffsets = expInfo.paOuterOffsets.slice(0, 2);

  for (const category of ['A', 'B']) {
    const sign = category === 'A' ? 1 : -1;
    const center = category === 'A' ? categoryGeometry.centerA : categoryGeometry.centerB;

    for (const axisOffset of axisOffsets) {
      const axisPt = shiftPoint(center, T_MAJOR, axisOffset);
      if (pointInCategory(axisPt, category)) {
        const uv = projectToSpaceFrame(axisPt.x, axisPt.y);
        points.push({
          x: axisPt.x,
          y: axisPt.y,
          u: uv.tCoord,
          v: uv.nCoord,
          category,
          probeFamily: 'inside',
          axisOffset,
          outerOffset: 0,
        });
      }

      for (const outerOffset of outerOffsets) {
        let p = shiftPoint(axisPt, N_MINOR, sign * outerOffset);
        for (let k = 0; k < 6 && pointInCategoryEllipse(p, category); k++) {
          p = shiftPoint(p, N_MINOR, sign * 2);
        }
        if (!inBounds(p.x, p.y) || !pointOnCategorySide(p, category)) continue;
        const uv = projectToSpaceFrame(p.x, p.y);
        points.push({
          x: p.x,
          y: p.y,
          u: uv.tCoord,
          v: uv.nCoord,
          category,
          probeFamily: 'outer',
          axisOffset,
          outerOffset,
        });
      }
    }
  }

  if (points.length === 0) {
    const fallback = samplePointInCategory('A');
    const uv = projectToSpaceFrame(fallback.x, fallback.y);
    points.push({
      x: fallback.x,
      y: fallback.y,
      u: uv.tCoord,
      v: uv.nCoord,
      category: 'A',
      probeFamily: 'inside',
      axisOffset: 0,
      outerOffset: 0,
    });
  }
  return points;
}

function makeAcuityStaircases() {
  const cfg = profile.acuity;
  const points = makeAcuityPoints();
  const scList = [];

  for (let pIdx = 0; pIdx < points.length; pIdx++) {
    for (let aIdx = 0; aIdx < cfg.axes.length; aIdx++) {
      const axis = cfg.axes[aIdx];
      const id = `p${pIdx}_a${aIdx}`;
      scList.push({
        id,
        pointIdx: pIdx,
        x: points[pIdx].x,
        y: points[pIdx].y,
        u: points[pIdx].u,
        v: points[pIdx].v,
        category: points[pIdx].category,
        probeFamily: points[pIdx].probeFamily,
        axisOffset: points[pIdx].axisOffset,
        outerOffset: points[pIdx].outerOffset,
        angleDeg: axis.angleDeg,
        axisType: axis.axisType,
        delta: cfg.deltaInit,
        nTrials: 0,
        nCorrectInRow: 0,
        reversals: 0,
        lastDirection: 0,
        done: false,
      });
    }
  }
  return scList;
}

function makeAcuityTrialOrder(scList) {
  const ids = scList.map((s) => s.id);
  const out = [];
  const maxTrials = profile.acuity.maxTrials;

  for (let r = 0; r < maxTrials; r++) {
    const round = [...ids];
    shuffle(round);
    for (const id of round) {
      out.push(mkTrialBase({ mode: MODE_ACUITY, scId: id, round: r + 1 }));
    }
  }

  if (profile.blockBreaks.length > 0) {
    const withBreaks = [];
    let mainCount = 0;
    let breakIdx = 0;
    for (const tr of out) {
      if (breakIdx < profile.blockBreaks.length && mainCount === profile.blockBreaks[breakIdx]) {
        withBreaks.push(mkTrialBase({ mode: 'break', trialType: 'break', breakIndex: breakIdx + 1 }));
        breakIdx += 1;
      }
      withBreaks.push(tr);
      mainCount += 1;
    }
    return withBreaks;
  }

  return out;
}

function makeAcuityPair(sc) {
  const cfg = profile.acuity;
  const dir = unitFromAngleDeg(sc.angleDeg);
  let delta = clamp(sc.delta, cfg.deltaMin, cfg.deltaMax);
  const base = { x: sc.x, y: sc.y };

  for (let tries = 0; tries < 8; tries++) {
    const comp = {
      x: clamp(sc.x + dir[0] * delta, X_MIN, X_MAX),
      y: clamp(sc.y + dir[1] * delta, Y_MIN, Y_MAX),
    };
    if (hasVisibleDifference(base, comp)) return { base, comp, delta };
    delta = clamp(delta * 0.75, cfg.deltaMin, cfg.deltaMax);
  }

  const fallback = {
    x: clamp(sc.x - dir[0] * cfg.deltaMin, X_MIN, X_MAX),
    y: clamp(sc.y - dir[1] * cfg.deltaMin, Y_MIN, Y_MAX),
  };
  return { base, comp: fallback, delta: cfg.deltaMin };
}

function makeCpConditions() {
  const dists = [
    { level: 'near', distance: expInfo.cpDistSmall },
    { level: 'far', distance: expInfo.cpDistLarge },
  ];
  const families = ['within_A', 'within_B', 'between_AB'];
  const out = [];
  for (const family of families) {
    for (const d of dists) out.push({ family, distanceLevel: d.level, distance: d.distance });
  }
  return out;
}

function sampleWithinPair(category, distance) {
  for (let k = 0; k < 500; k++) {
    const center = samplePointInCategory(category);
    const p1 = shiftPoint(center, T_MAJOR, distance * 0.5);
    const p2 = shiftPoint(center, T_MAJOR, -distance * 0.5);
    if (pointInCategory(p1, category) && pointInCategory(p2, category)) {
      return { ref: p1, cmp: p2 };
    }
  }
  const center = samplePointInCategory(category);
  return { ref: center, cmp: shiftPoint(center, T_MAJOR, 0.01) };
}

function sampleBetweenPair(distance) {
  for (let k = 0; k < 500; k++) {
    const t = randIn(0.15, 0.85);
    const mid = { x: X_MIN + (X_MAX - X_MIN) * t, y: Y_MIN + (Y_MAX - Y_MIN) * t };
    const pA = shiftPoint(mid, N_MINOR, distance * 0.5);
    const pB = shiftPoint(mid, N_MINOR, -distance * 0.5);
    if (pointInCategory(pA, 'A') && pointInCategory(pB, 'B')) {
      return { ref: pA, cmp: pB };
    }
  }
  return { ref: shiftPoint(SPACE_CENTER, N_MINOR, 0.5), cmp: shiftPoint(SPACE_CENTER, N_MINOR, -0.5) };
}

function makeCpPairPointsFromCell(cell) {
  if (cell.family === 'within_A') return sampleWithinPair('A', cell.distance);
  if (cell.family === 'within_B') return sampleWithinPair('B', cell.distance);
  return sampleBetweenPair(cell.distance);
}

function cellToLegacyFields(cell) {
  if (cell.family === 'within_A') return { pairType: 'within', side: 1 };
  if (cell.family === 'within_B') return { pairType: 'within', side: -1 };
  return { pairType: 'across', side: 0 };
}

function makeCpTrials() {
  const cfg = profile.cp;
  const trials = [];
  const cells = makeCpConditions();

  if (profile.practiceTrials > 0) {
    const practiceCells = [...cells];
    shuffle(practiceCells);
    for (let i = 0; i < profile.practiceTrials; i++) {
      const cell = practiceCells[i % practiceCells.length];
      trials.push(mkTrialBase({
        mode: MODE_CP,
        trialType: 'practice',
        blockId: 0,
        cell,
        conditionId: `practice_${cell.family}_${cell.distanceLevel}_${cell.distance.toFixed(3)}`,
      }));
    }
  }

  const mains = [];
  for (const cell of cells) {
    for (let r = 0; r < cfg.repsPerCondition; r++) {
      mains.push(mkTrialBase({
        mode: MODE_CP,
        trialType: 'main',
        cell,
        conditionId: `${cell.family}_${cell.distanceLevel}_${cell.distance.toFixed(3)}`,
      }));
    }
  }
  shuffle(mains);

  currentBlockId = 1;
  const withBreaks = [];
  let mainCount = 0;
  let breakIdx = 0;
  for (const tr of mains) {
    if (breakIdx < profile.blockBreaks.length && mainCount === profile.blockBreaks[breakIdx]) {
      withBreaks.push(mkTrialBase({ mode: 'break', trialType: 'break', breakIndex: breakIdx + 1 }));
      breakIdx += 1;
      currentBlockId += 1;
    }
    tr.blockId = currentBlockId;
    withBreaks.push(tr);
    mainCount += 1;
  }

  return trials.concat(withBreaks);
}

function makeTrials() {
  if (expInfo.mode === MODE_ACUITY) {
    staircases = makeAcuityStaircases();
    staircasesById = new Map(staircases.map((s) => [s.id, s]));
    return makeAcuityTrialOrder(staircases);
  }

  return makeCpTrials();
}

function setupCpTrialRuntime(trial, idx) {
  const cell = trial.cell;
  const pair = makeCpPairPointsFromCell(cell);
  const legacy = cellToLegacyFields(cell);

  const diffInterval = rand() < 0.5 ? 1 : 2;
  const flipDiffOrder = rand() < 0.5;

  const samePair = { a: pair.ref, b: pair.ref };
  const diffPair = flipDiffOrder ? { a: pair.cmp, b: pair.ref } : { a: pair.ref, b: pair.cmp };
  const interval1 = diffInterval === 1 ? diffPair : samePair;
  const interval2 = diffInterval === 2 ? diffPair : samePair;

  return {
    trialIndex: idx,
    mode: MODE_CP,
    trialType: trial.trialType,
    blockId: trial.blockId,
    conditionId: trial.conditionId,
    pairType: legacy.pairType,
    band: cell.distanceLevel,
    side: legacy.side,
    cpFamily: cell.family,
    cpDistanceLevel: cell.distanceLevel,
    distance: cell.distance,
    int1a: interval1.a,
    int1b: interval1.b,
    int2a: interval2.a,
    int2b: interval2.b,
    diffInterval,
    key: null,
    rtSec: null,
    correct: false,
  };
}

async function updateInfo() {
  expInfo.date = util.MonotonicClock.getDateStr();
  expInfo.expName = EXP_NAME;
  util.addInfoFromUrl(expInfo);

  const url = new URL(window.location.href);
  const q = url.searchParams;
  expInfo.participant = q.get('participant') || expInfo.participant || '999';
  expInfo.session = q.get('session') || expInfo.session || '001';
  expInfo.day = q.get('day') || expInfo.day || 'unspecified';
  expInfo.mode = q.get('mode') || expInfo.mode || MODE_ACUITY;
  expInfo.design = q.get('design') || expInfo.design || DESIGN_PILOT;
  expInfo.seed = q.get('seed') || expInfo.seed || `${expInfo.participant}_${expInfo.session}_${expInfo.mode}_${expInfo.day}`;
  expInfo.debugPreview = parseBoolParam(q.get('debug_preview'));
  expInfo.catAxisGap = parseFloatParam(q.get('cat_axis_gap'), expInfo.catAxisGap);
  expInfo.catMajorAxisFrac = parseFloatParam(q.get('cat_major_axis_frac'), expInfo.catMajorAxisFrac);
  expInfo.catMinorAxisLen = parseFloatParam(q.get('cat_minor_axis_len'), expInfo.catMinorAxisLen);
  expInfo.paAxisOffsets = parseFloatListParam(q.get('pa_axis_offsets'), expInfo.paAxisOffsets);
  expInfo.paOuterOffsets = parseFloatListParam(q.get('pa_outer_offsets'), expInfo.paOuterOffsets);
  expInfo.cpDistSmall = parseFloatParam(q.get('cp_dist_small'), expInfo.cpDistSmall);
  expInfo.cpDistLarge = parseFloatParam(q.get('cp_dist_large'), expInfo.cpDistLarge);

  if (![MODE_ACUITY, MODE_CP].includes(expInfo.mode)) expInfo.mode = MODE_ACUITY;
  if (![DESIGN_PILOT, DESIGN_FULL].includes(expInfo.design)) expInfo.design = DESIGN_PILOT;
  expInfo.catAxisGap = clamp(expInfo.catAxisGap, 0, SPACE_DIAG * 0.7);
  expInfo.catMajorAxisFrac = clamp(expInfo.catMajorAxisFrac, 0.05, 0.95);
  expInfo.catMinorAxisLen = clamp(expInfo.catMinorAxisLen, 1, SPACE_DIAG * 0.7);
  expInfo.paAxisOffsets = expInfo.paAxisOffsets.length >= 2 ? expInfo.paAxisOffsets : [-18, 18];
  expInfo.paOuterOffsets = expInfo.paOuterOffsets.length >= 2 ? expInfo.paOuterOffsets : [10, 18];
  expInfo.cpDistSmall = Math.max(0.5, expInfo.cpDistSmall);
  expInfo.cpDistLarge = Math.max(expInfo.cpDistSmall + 0.5, expInfo.cpDistLarge);

  profile = PROFILE_BY_MODE[expInfo.mode][expInfo.design];
  categoryGeometry = createCategoryGeometry();
  rng = makeSeededRng(expInfo.seed);

  return Scheduler.Event.NEXT;
}

async function experimentInit() {
  routineClock = new util.Clock();

  infoText = new visual.TextStim({
    win: psychoJS.window,
    text: '',
    height: 0.035,
    color: new util.Color('white'),
    wrapWidth: 1.5,
  });

  promptText = new visual.TextStim({
    win: psychoJS.window,
    text: '',
    height: 0.04,
    color: new util.Color('white'),
    wrapWidth: 1.5,
    pos: [0, -0.2],
  });

  intervalText = new visual.TextStim({
    win: psychoJS.window,
    text: '',
    height: 0.045,
    color: new util.Color('white'),
    pos: [0, 0.22],
  });

  debugPreviewText = new visual.TextStim({
    win: psychoJS.window,
    text: '',
    height: 0.028,
    color: new util.Color('white'),
    wrapWidth: 1.6,
    pos: [0, -0.28],
  });

  fixH = new visual.ShapeStim({
    win: psychoJS.window,
    vertices: [[-0.02, 0], [0.02, 0]],
    lineWidth: 6,
    lineColor: new util.Color('white'),
    fillColor: undefined,
    closeShape: false,
    pos: [0, 0],
  });

  fixV = new visual.ShapeStim({
    win: psychoJS.window,
    vertices: [[0, -0.02], [0, 0.02]],
    lineWidth: 6,
    lineColor: new util.Color('white'),
    fillColor: undefined,
    closeShape: false,
    pos: [0, 0],
  });

  grating = new visual.GratingStim({
    win: psychoJS.window,
    tex: 'sin',
    mask: 'circle',
    units: 'height',
    size: [0.34, 0.34],
    sf: 3,
    ori: 0,
    phase: 0,
    pos: [0, 0],
  });

  previewGratings = PREVIEW_X_POSITIONS.map((x) => (
    new visual.GratingStim({
      win: psychoJS.window,
      tex: 'sin',
      mask: 'circle',
      units: 'height',
      size: [0.19, 0.19],
      sf: 3,
      ori: 0,
      phase: 0,
      pos: [x, PREVIEW_Y],
    })
  ));

  previewLabels = PREVIEW_LABELS.map((text, i) => (
    new visual.TextStim({
      win: psychoJS.window,
      text,
      height: 0.03,
      color: new util.Color('white'),
      pos: [PREVIEW_X_POSITIONS[i], PREVIEW_Y - 0.16],
    })
  ));

  previewValueTexts = PREVIEW_LABELS.map((_, i) => (
    new visual.TextStim({
      win: psychoJS.window,
      text: '',
      height: 0.022,
      color: new util.Color('white'),
      pos: [PREVIEW_X_POSITIONS[i], PREVIEW_Y + 0.17],
      wrapWidth: 0.28,
    })
  ));

  previewOddHighlight = new visual.Rect({
    win: psychoJS.window,
    units: 'height',
    width: PREVIEW_STIM_SIZE + 0.06,
    height: PREVIEW_STIM_SIZE + 0.06,
    lineWidth: 4,
    lineColor: new util.Color('green'),
    fillColor: undefined,
    pos: [0, PREVIEW_Y],
  });

  fixH.setAutoDraw(false);
  fixV.setAutoDraw(false);
  grating.setAutoDraw(false);
  infoText.setAutoDraw(false);
  promptText.setAutoDraw(false);
  intervalText.setAutoDraw(false);
  debugPreviewText.setAutoDraw(false);
  for (const g of previewGratings) g.setAutoDraw(false);
  for (const t of previewLabels) t.setAutoDraw(false);
  for (const t of previewValueTexts) t.setAutoDraw(false);
  previewOddHighlight.setAutoDraw(false);

  return Scheduler.Event.NEXT;
}

function instructionsBegin() {
  return async function () {
    psychoJS.eventManager.clearEvents();
    routineClock.reset();

    const modeLine = `Mode: ${expInfo.mode} | Design: ${expInfo.design}`;
    const idLine = `Participant ${expInfo.participant} | Session ${expInfo.session} | Day ${expInfo.day}`;
    const seedLine = `Seed: ${expInfo.seed}`;

    const controls = 'Task: Which interval contained the within-interval change? (1/2 keys)';
    infoText.text = `${modeLine}\n${idLine}\n${seedLine}\n\n${controls}\n\nPress space to start`;
    infoText.setAutoDraw(true);
    return Scheduler.Event.NEXT;
  };
}

function instructionsEachFrame() {
  return async function () {
    const keys = psychoJS.eventManager.getKeys({ keyList: ['space', 'escape'] });
    if (keys.length > 0) {
      const k = keys[keys.length - 1];
      if (k === 'escape') return quitPsychoJS('Quit', false);
      if (k === 'space') return Scheduler.Event.NEXT;
    }
    return Scheduler.Event.FLIP_REPEAT;
  };
}

function instructionsEnd() {
  return async function () {
    infoText.setAutoDraw(false);
    return Scheduler.Event.NEXT;
  };
}

async function trialLoopInit() {
  allTrials = makeTrials();
  breakCursor = 0;
  doneMainCount = 0;
  currentBlockId = 1;
  blockComplete = false;
  return Scheduler.Event.NEXT;
}

function trialBegin(idx) {
  return async function () {
    trialDone = false;
    skipTrial = false;
    sawBreakThisTrial = false;
    hideDebugPreview();

    if (blockComplete || idx >= allTrials.length) {
      blockComplete = true;
      skipTrial = true;
      return Scheduler.Event.NEXT;
    }

    currentTrial = allTrials[idx];

    if (currentTrial.mode === 'break') {
      phase = 'break_wait';
      routineClock.reset();
      infoText.text = `Break ${currentTrial.breakIndex}.\n\nPress space to continue.`;
      infoText.setAutoDraw(true);
      psychoJS.eventManager.clearEvents();
      trialRuntime = {
        trialIndex: idx,
        mode: 'break',
        trialType: 'break',
        blockId: currentBlockId,
        conditionId: `break_${currentTrial.breakIndex}`,
      };
      return Scheduler.Event.NEXT;
    }

    if (currentTrial.mode === MODE_ACUITY) {
      const sc = staircasesById.get(currentTrial.scId);
      if (!sc || sc.done) {
        skipTrial = true;
        if (staircases.every((s) => s.done)) blockComplete = true;
        return Scheduler.Event.NEXT;
      }

      const pair = makeAcuityPair(sc);
      const diffInterval = rand() < 0.5 ? 1 : 2;
      const flipDiffOrder = rand() < 0.5;

      const samePair = { a: pair.base, b: pair.base };
      const diffPair = flipDiffOrder ? { a: pair.comp, b: pair.base } : { a: pair.base, b: pair.comp };
      const interval1 = diffInterval === 1 ? diffPair : samePair;
      const interval2 = diffInterval === 2 ? diffPair : samePair;

      trialRuntime = {
        trialIndex: idx,
        mode: MODE_ACUITY,
        trialType: currentTrial.trialType,
        blockId: currentTrial.blockId,
        conditionId: currentTrial.conditionId || `sc_${sc.id}`,
        scId: sc.id,
        gridX: sc.x,
        gridY: sc.y,
        u: sc.u,
        v: sc.v,
        category: sc.category,
        probeFamily: sc.probeFamily,
        axisOffset: sc.axisOffset,
        outerOffset: sc.outerOffset,
        angleDeg: sc.angleDeg,
        axisType: sc.axisType,
        delta: pair.delta,
        int1a: interval1.a,
        int1b: interval1.b,
        int2a: interval2.a,
        int2b: interval2.b,
        diffInterval,
        key: null,
        rtSec: null,
        correct: false,
      };
    } else {
      trialRuntime = setupCpTrialRuntime(currentTrial, idx);
    }

    phase = 'iti';
    routineClock.reset();
    psychoJS.eventManager.clearEvents();
    fixH.setAutoDraw(true);
    fixV.setAutoDraw(true);
    grating.setAutoDraw(false);
    promptText.setAutoDraw(false);
    intervalText.setAutoDraw(false);
    infoText.setAutoDraw(false);

    const jitter = profile.timings.itiJitterSec || [0, 0];
    jitteredItiSec = profile.timings.itiSec + randIn(jitter[0], jitter[1]);

    return Scheduler.Event.NEXT;
  };
}

function setGratingFromPoint(pt) {
  const p = toStimParams(pt.x, pt.y);
  grating.sf = p.sf;
  grating.ori = p.oriDeg;
  grating.phase = 0;
}

function hideDebugPreview() {
  debugPreviewText.setAutoDraw(false);
  for (const g of previewGratings) g.setAutoDraw(false);
  for (const t of previewLabels) t.setAutoDraw(false);
  for (const t of previewValueTexts) t.setAutoDraw(false);
  previewOddHighlight.setAutoDraw(false);
}

function showDebugPreviewFromTrialRuntime() {
  const pts = [trialRuntime.int1a, trialRuntime.int1b, trialRuntime.int2a, trialRuntime.int2b];
  const sigToCount = new Map();
  const signatures = pts.map((pt) => `${Math.round(pt.x * 1000)},${Math.round(pt.y * 1000)}`);

  for (const sig of signatures) {
    sigToCount.set(sig, (sigToCount.get(sig) || 0) + 1);
  }

  let oddIdx = -1;
  for (let i = 0; i < signatures.length; i++) {
    if ((sigToCount.get(signatures[i]) || 0) === 1) {
      oddIdx = i;
      break;
    }
  }

  for (let i = 0; i < pts.length; i++) {
    const p = toStimParams(pts[i].x, pts[i].y);
    const g = previewGratings[i];
    const label = previewLabels[i];
    const valueText = previewValueTexts[i];
    g.sf = p.sf;
    g.ori = p.oriDeg;
    g.phase = 0;
    g.pos = [PREVIEW_X_POSITIONS[i], PREVIEW_Y];
    label.pos = [PREVIEW_X_POSITIONS[i], PREVIEW_Y - 0.16];
    valueText.pos = [PREVIEW_X_POSITIONS[i], PREVIEW_Y + 0.17];
    valueText.text = `sf ${p.sf.toFixed(2)}\nori ${p.oriDeg.toFixed(1)}°`;
    g.setAutoDraw(true);
    label.setAutoDraw(true);
    valueText.setAutoDraw(true);
  }

  if (oddIdx >= 0) {
    previewOddHighlight.pos = [PREVIEW_X_POSITIONS[oddIdx], PREVIEW_Y];
    previewOddHighlight.setAutoDraw(true);
  } else {
    previewOddHighlight.setAutoDraw(false);
  }

  debugPreviewText.text = 'Debug PA preview (last trial): I1A  I1B  I2A  I2B\nPress space for next trial';
  debugPreviewText.setAutoDraw(true);
}

function trialEachFrame() {
  return async function () {
    if (skipTrial || blockComplete) return Scheduler.Event.NEXT;

    const t = routineClock.getTime();

    if (phase === 'break_wait') {
      const keys = psychoJS.eventManager.getKeys({ keyList: ['space', 'escape'] });
      if (keys.length > 0) {
        const k = keys[keys.length - 1];
        if (k === 'escape') return quitPsychoJS('Quit', false);
        if (k === 'space') {
          infoText.setAutoDraw(false);
          sawBreakThisTrial = true;
          trialDone = true;
          return Scheduler.Event.NEXT;
        }
      }
      return Scheduler.Event.FLIP_REPEAT;
    }

    if (phase === 'iti') {
      if (t >= jitteredItiSec) {
        phase = 'int1a';
        routineClock.reset();
        fixH.setAutoDraw(false);
        fixV.setAutoDraw(false);
        setGratingFromPoint(trialRuntime.int1a);
        intervalText.text = 'Interval 1 (1/2)';
        intervalText.setAutoDraw(true);
        grating.setAutoDraw(true);
      }
      return Scheduler.Event.FLIP_REPEAT;
    }

    if (phase === 'int1a') {
      if (t >= profile.timings.intervalSec) {
        phase = 'int1gap';
        routineClock.reset();
        grating.setAutoDraw(false);
        fixH.setAutoDraw(true);
        fixV.setAutoDraw(true);
      }
      return Scheduler.Event.FLIP_REPEAT;
    }

    if (phase === 'int1gap') {
      if (t >= profile.timings.pairGapSec) {
        phase = 'int1b';
        routineClock.reset();
        fixH.setAutoDraw(false);
        fixV.setAutoDraw(false);
        setGratingFromPoint(trialRuntime.int1b);
        intervalText.text = 'Interval 1 (2/2)';
        grating.setAutoDraw(true);
      }
      return Scheduler.Event.FLIP_REPEAT;
    }

    if (phase === 'int1b') {
      if (t >= profile.timings.intervalSec) {
        phase = 'isi';
        routineClock.reset();
        grating.setAutoDraw(false);
        intervalText.setAutoDraw(false);
        fixH.setAutoDraw(true);
        fixV.setAutoDraw(true);
      }
      return Scheduler.Event.FLIP_REPEAT;
    }

    if (phase === 'isi') {
      if (t >= profile.timings.isiSec) {
        phase = 'int2a';
        routineClock.reset();
        fixH.setAutoDraw(false);
        fixV.setAutoDraw(false);
        setGratingFromPoint(trialRuntime.int2a);
        intervalText.text = 'Interval 2 (1/2)';
        intervalText.setAutoDraw(true);
        grating.setAutoDraw(true);
      }
      return Scheduler.Event.FLIP_REPEAT;
    }

    if (phase === 'int2a') {
      if (t >= profile.timings.intervalSec) {
        phase = 'int2gap';
        routineClock.reset();
        grating.setAutoDraw(false);
        fixH.setAutoDraw(true);
        fixV.setAutoDraw(true);
      }
      return Scheduler.Event.FLIP_REPEAT;
    }

    if (phase === 'int2gap') {
      if (t >= profile.timings.pairGapSec) {
        phase = 'int2b';
        routineClock.reset();
        fixH.setAutoDraw(false);
        fixV.setAutoDraw(false);
        setGratingFromPoint(trialRuntime.int2b);
        intervalText.text = 'Interval 2 (2/2)';
        grating.setAutoDraw(true);
      }
      return Scheduler.Event.FLIP_REPEAT;
    }

    if (phase === 'int2b') {
      if (t >= profile.timings.intervalSec) {
        phase = 'resp';
        routineClock.reset();
        grating.setAutoDraw(false);
        intervalText.setAutoDraw(false);
        promptText.text = 'Which interval contained the within-interval change?\nPress 1 or 2';
        promptText.setAutoDraw(true);
        psychoJS.eventManager.clearEvents();
      }
      return Scheduler.Event.FLIP_REPEAT;
    }

    if (phase === 'resp') {
      const keys = psychoJS.eventManager.getKeys({ keyList: ['1', '2', 'num_1', 'num_2', 'escape'] });
      if (keys.length > 0) {
        const raw = keys[keys.length - 1];
        if (raw === 'escape') return quitPsychoJS('Quit', false);

        let key = raw;
        if (key === 'num_1') key = '1';
        if (key === 'num_2') key = '2';

        trialRuntime.key = key;
        trialRuntime.rtSec = routineClock.getTime();
        trialRuntime.correct = Number(key) === trialRuntime.diffInterval;

        promptText.setAutoDraw(false);
        if (trialRuntime.mode === MODE_ACUITY && expInfo.debugPreview) {
          phase = 'debug_preview';
          routineClock.reset();
          showDebugPreviewFromTrialRuntime();
          psychoJS.eventManager.clearEvents();
          return Scheduler.Event.FLIP_REPEAT;
        }
        trialDone = true;
        return Scheduler.Event.NEXT;
      }

      if (profile.timings.respWindowSec != null && t >= profile.timings.respWindowSec) {
        trialRuntime.key = 'none';
        trialRuntime.rtSec = null;
        trialRuntime.correct = false;
        promptText.setAutoDraw(false);
        if (trialRuntime.mode === MODE_ACUITY && expInfo.debugPreview) {
          phase = 'debug_preview';
          routineClock.reset();
          showDebugPreviewFromTrialRuntime();
          psychoJS.eventManager.clearEvents();
          return Scheduler.Event.FLIP_REPEAT;
        }
        trialDone = true;
        return Scheduler.Event.NEXT;
      }

      return Scheduler.Event.FLIP_REPEAT;
    }

    if (phase === 'debug_preview') {
      const keys = psychoJS.eventManager.getKeys({ keyList: ['space', 'escape'] });
      if (keys.length > 0) {
        const k = keys[keys.length - 1];
        if (k === 'escape') return quitPsychoJS('Quit', false);
        if (k === 'space') {
          hideDebugPreview();
          trialDone = true;
          return Scheduler.Event.NEXT;
        }
      }
      return Scheduler.Event.FLIP_REPEAT;
    }

    return Scheduler.Event.FLIP_REPEAT;
  };
}

function updateAcuityStaircase(sc, isCorrect) {
  const cfg = profile.acuity;

  sc.nTrials += 1;
  let direction = 0;

  if (isCorrect) {
    sc.nCorrectInRow += 1;
    if (sc.nCorrectInRow >= 2) {
      sc.nCorrectInRow = 0;
      sc.delta = clamp(sc.delta * cfg.downGain, cfg.deltaMin, cfg.deltaMax);
      direction = -1;
    }
  } else {
    sc.nCorrectInRow = 0;
    sc.delta = clamp(sc.delta * cfg.upGain, cfg.deltaMin, cfg.deltaMax);
    direction = 1;
  }

  if (direction !== 0 && sc.lastDirection !== 0 && direction !== sc.lastDirection) {
    sc.reversals += 1;
  }
  if (direction !== 0) sc.lastDirection = direction;

  if (sc.nTrials >= cfg.maxTrials || sc.reversals >= cfg.maxReversals) {
    sc.done = true;
  }
}

function trialEnd(idx) {
  return async function () {
    if (skipTrial || !trialDone) return Scheduler.Event.NEXT;

    const ts = nowISO();

    psychoJS.experiment.addData('participant', expInfo.participant);
    psychoJS.experiment.addData('session', expInfo.session);
    psychoJS.experiment.addData('day', expInfo.day);
    psychoJS.experiment.addData('mode', trialRuntime.mode);
    psychoJS.experiment.addData('design', expInfo.design);
    psychoJS.experiment.addData('seed', expInfo.seed);
    psychoJS.experiment.addData('debug_preview_enabled', expInfo.debugPreview ? 1 : 0);
    psychoJS.experiment.addData('cat_axis_gap', expInfo.catAxisGap);
    psychoJS.experiment.addData('cat_major_axis_frac', expInfo.catMajorAxisFrac);
    psychoJS.experiment.addData('cat_minor_axis_len', expInfo.catMinorAxisLen);
    psychoJS.experiment.addData('pa_axis_offsets', expInfo.paAxisOffsets.join(','));
    psychoJS.experiment.addData('pa_outer_offsets', expInfo.paOuterOffsets.join(','));
    psychoJS.experiment.addData('cp_dist_small', expInfo.cpDistSmall);
    psychoJS.experiment.addData('cp_dist_large', expInfo.cpDistLarge);
    psychoJS.experiment.addData('trial_index', idx);
    psychoJS.experiment.addData('trial_type', trialRuntime.trialType);
    psychoJS.experiment.addData('block_id', trialRuntime.blockId ?? null);
    psychoJS.experiment.addData('condition_id', trialRuntime.conditionId ?? null);
    psychoJS.experiment.addData('completion_flag', blockComplete ? 'complete' : 'in_progress');

    if (trialRuntime.mode === 'break') {
      psychoJS.experiment.addData('event', 'break');
      psychoJS.experiment.addData('ts_iso', ts);
      psychoJS.experiment.nextEntry();
      trialDone = false;
      return Scheduler.Event.NEXT;
    }

    psychoJS.experiment.addData('key', trialRuntime.key);
    psychoJS.experiment.addData('rt_ms', trialRuntime.rtSec == null ? null : trialRuntime.rtSec * 1000);
    psychoJS.experiment.addData('correct', trialRuntime.correct ? 1 : 0);

    psychoJS.experiment.addData('i1a_x', trialRuntime.int1a.x);
    psychoJS.experiment.addData('i1a_y', trialRuntime.int1a.y);
    psychoJS.experiment.addData('i1b_x', trialRuntime.int1b.x);
    psychoJS.experiment.addData('i1b_y', trialRuntime.int1b.y);
    psychoJS.experiment.addData('i2a_x', trialRuntime.int2a.x);
    psychoJS.experiment.addData('i2a_y', trialRuntime.int2a.y);
    psychoJS.experiment.addData('i2b_x', trialRuntime.int2b.x);
    psychoJS.experiment.addData('i2b_y', trialRuntime.int2b.y);
    psychoJS.experiment.addData('diff_interval', trialRuntime.diffInterval);
    psychoJS.experiment.addData('interval1_changed', hasVisibleDifference(trialRuntime.int1a, trialRuntime.int1b) ? 1 : 0);
    psychoJS.experiment.addData('interval2_changed', hasVisibleDifference(trialRuntime.int2a, trialRuntime.int2b) ? 1 : 0);

    if (trialRuntime.mode === MODE_ACUITY) {
      const sc = staircasesById.get(trialRuntime.scId);
      updateAcuityStaircase(sc, trialRuntime.correct);

      psychoJS.experiment.addData('sc_id', trialRuntime.scId);
      psychoJS.experiment.addData('grid_x', trialRuntime.gridX);
      psychoJS.experiment.addData('grid_y', trialRuntime.gridY);
      psychoJS.experiment.addData('u', trialRuntime.u);
      psychoJS.experiment.addData('v', trialRuntime.v);
      psychoJS.experiment.addData('category', trialRuntime.category);
      psychoJS.experiment.addData('probe_family', trialRuntime.probeFamily);
      psychoJS.experiment.addData('axis_offset', trialRuntime.axisOffset);
      psychoJS.experiment.addData('outer_offset', trialRuntime.outerOffset);
      psychoJS.experiment.addData('angle_deg', trialRuntime.angleDeg);
      psychoJS.experiment.addData('axis_type', trialRuntime.axisType);
      psychoJS.experiment.addData('delta_used', trialRuntime.delta);
      psychoJS.experiment.addData('sc_trials_done', sc.nTrials);
      psychoJS.experiment.addData('sc_reversals', sc.reversals);
      psychoJS.experiment.addData('sc_delta_next', sc.delta);
      psychoJS.experiment.addData('sc_done', sc.done ? 1 : 0);

      if (trialRuntime.trialType === 'main') doneMainCount += 1;
      if (staircases.every((s) => s.done)) blockComplete = true;
    } else {
      psychoJS.experiment.addData('pair_type', trialRuntime.pairType);
      psychoJS.experiment.addData('band', trialRuntime.band);
      psychoJS.experiment.addData('side', trialRuntime.side);
      psychoJS.experiment.addData('cp_family', trialRuntime.cpFamily);
      psychoJS.experiment.addData('cp_distance_level', trialRuntime.cpDistanceLevel);
      psychoJS.experiment.addData('u_anchor', null);
      psychoJS.experiment.addData('distance', trialRuntime.distance);
      psychoJS.experiment.addData('signed_dist_i1a', signedBoundaryDistance(trialRuntime.int1a.x, trialRuntime.int1a.y));
      psychoJS.experiment.addData('signed_dist_i1b', signedBoundaryDistance(trialRuntime.int1b.x, trialRuntime.int1b.y));
      psychoJS.experiment.addData('signed_dist_i2a', signedBoundaryDistance(trialRuntime.int2a.x, trialRuntime.int2a.y));
      psychoJS.experiment.addData('signed_dist_i2b', signedBoundaryDistance(trialRuntime.int2b.x, trialRuntime.int2b.y));

      if (trialRuntime.trialType === 'main') doneMainCount += 1;
      if (doneMainCount >= allTrials.filter((t) => t.mode !== 'break' && t.trialType === 'main').length) {
        blockComplete = true;
      }
    }

    psychoJS.experiment.addData('event', sawBreakThisTrial ? 'break_resume' : 'trial');
    psychoJS.experiment.addData('ts_iso', ts);
    psychoJS.experiment.nextEntry();

    trialDone = false;
    return Scheduler.Event.NEXT;
  };
}

async function finalizeData() {
  const pid = fmt3(expInfo.participant);
  const session = fmt3(expInfo.session);
  const filename = `sub_${pid}_sess_${session}_${expInfo.mode}_${expInfo.design}_web.csv`;
  await psychoJS.experiment.save({ attributes: [], sync: true, tag: filename, clear: false });
  return Scheduler.Event.NEXT;
}

function doneBegin() {
  return async function () {
    routineClock.reset();
    fixH.setAutoDraw(false);
    fixV.setAutoDraw(false);
    grating.setAutoDraw(false);
    promptText.setAutoDraw(false);
    intervalText.setAutoDraw(false);
    hideDebugPreview();
    infoText.text = 'Block complete.\n\nThank you!';
    infoText.setAutoDraw(true);
    return Scheduler.Event.NEXT;
  };
}

function doneEachFrame() {
  return async function () {
    const keys = psychoJS.eventManager.getKeys({ keyList: ['escape'] });
    if (keys.length > 0) return Scheduler.Event.NEXT;
    if (routineClock.getTime() >= 1.0) return Scheduler.Event.NEXT;
    return Scheduler.Event.FLIP_REPEAT;
  };
}

function doneEnd() {
  return async function () {
    infoText.setAutoDraw(false);
    return Scheduler.Event.NEXT;
  };
}

function quitPsychoJS(message, isCompleted) {
  psychoJS.window.close();
  psychoJS.quit({ message, isCompleted });
  return Scheduler.Event.QUIT;
}
