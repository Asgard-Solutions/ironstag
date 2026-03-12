export const BC_G_FIELDS = ['g1', 'g2', 'g3', 'g4', 'g5', 'g6', 'g7'] as const;
export const BC_MULE_DEER_G_FIELDS = ['g1', 'g2', 'g3', 'g4'] as const;
export const BC_H_FIELDS = ['h1', 'h2', 'h3', 'h4'] as const;
export const BC_PAIR_FIELDS = ['mainBeam', ...BC_G_FIELDS, ...BC_H_FIELDS] as const;
export const BC_EIGHTH_OPTIONS = ['0/8', '1/8', '2/8', '3/8', '4/8', '5/8', '6/8', '7/8'] as const;
export const BC_SCORE_TYPES = [
  'typical_whitetail_unofficial',
  'non_typical_whitetail_unofficial',
  'typical_mule_deer_unofficial',
  'non_typical_mule_deer_unofficial',
] as const;
export const BC_PAIR_LABELS: Record<BcPairField, string> = {
  mainBeam: 'F Main Beam',
  g1: 'G-1',
  g2: 'G-2',
  g3: 'G-3',
  g4: 'G-4',
  g5: 'G-5',
  g6: 'G-6',
  g7: 'G-7',
  h1: 'H-1',
  h2: 'H-2',
  h3: 'H-3',
  h4: 'H-4',
};

const ASYMMETRY_WARNING_THRESHOLD = 8;
const FRACTION_PATTERN = /^(?:(?<whole>\d+)\s+)?(?<num>\d+)\s*\/\s*(?<den>\d+)$/;

export type BcGField = (typeof BC_G_FIELDS)[number];
export type BcHField = (typeof BC_H_FIELDS)[number];
export type BcPairField = (typeof BC_PAIR_FIELDS)[number];
export type BcEighthOption = (typeof BC_EIGHTH_OPTIONS)[number];
export type BcScoreType = (typeof BC_SCORE_TYPES)[number];
export type BcScoreStatus = 'draft' | 'complete';

export interface BcScoreTypeOption {
  type: BcScoreType;
  label: string;
  deerType: 'Whitetail' | 'Mule Deer';
  implemented: boolean;
}

export const BC_SCORE_TYPE_OPTIONS: BcScoreTypeOption[] = [
  {
    type: 'typical_whitetail_unofficial',
    label: 'Typical Whitetail Deer',
    deerType: 'Whitetail',
    implemented: true,
  },
  {
    type: 'non_typical_whitetail_unofficial',
    label: 'Non-Typical Whitetail Deer',
    deerType: 'Whitetail',
    implemented: true,
  },
  {
    type: 'typical_mule_deer_unofficial',
    label: 'Typical Mule Deer',
    deerType: 'Mule Deer',
    implemented: true,
  },
  {
    type: 'non_typical_mule_deer_unofficial',
    label: 'Non-Typical Mule Deer',
    deerType: 'Mule Deer',
    implemented: true,
  },
];

export interface BcPointsSummary {
  rightPointsCount: number | null;
  leftPointsCount: number | null;
  tipToTipSpread: number | null;
  greatestSpread: number | null;
}

export interface BcSpread {
  insideSpreadOfMainBeams: number | null;
  spreadCredit?: number | null;
}

export interface BcAbnormalPoints {
  right: number[];
  left: number[];
  rightTotalLength?: number | null;
  leftTotalLength?: number | null;
  totalLength?: number | null;
}

export interface BcSideMeasurements {
  mainBeam: number | null;
  g1: number | null;
  g2: number | null;
  g3: number | null;
  g4: number | null;
  g5: number | null;
  g6: number | null;
  g7: number | null;
  h1: number | null;
  h2: number | null;
  h3: number | null;
  h4: number | null;
  extraPoints?: number[];
}

export interface BcComputed {
  rightTotal: number | null;
  leftTotal: number | null;
  subtotalOne: number | null;
  pairedDifferencesTotal: number | null;
  abnormalDeductionTotal: number | null;
  deductionsTotal: number | null;
  subtotalTwo: number | null;
  grossScore: number | null;
  finalScore: number | null;
}

export interface BcValidationWarning {
  code: string;
  message: string;
}

export interface BcScoreEntryInput {
  type?: BcScoreType;
  enteredManually?: true;
  disclaimerAccepted: boolean;
  pointsSummary: BcPointsSummary;
  spread: BcSpread;
  abnormalPoints: BcAbnormalPoints;
  right: BcSideMeasurements;
  left: BcSideMeasurements;
}

export interface BcScoreRecord extends BcScoreEntryInput {
  type: BcScoreType;
  status: BcScoreStatus;
  enteredManually: true;
  spread: BcSpread & { spreadCredit: number | null };
  abnormalPoints: BcAbnormalPoints & { totalLength: number | null };
  computed: BcComputed;
  differences: Record<string, number | null>;
  warnings: BcValidationWarning[];
  calculatedAt: string;
  updatedAt: string;
}

export interface BcScoreFormState {
  type: BcScoreType;
  disclaimerAccepted: boolean;
  pointsSummary: {
    rightPointsCount: string;
    leftPointsCount: string;
    tipToTipSpread: string;
    greatestSpread: string;
  };
  spread: {
    insideSpreadOfMainBeams: string;
  };
  abnormalPoints: {
    right: string[];
    left: string[];
  };
  right: Record<BcPairField, string> & { extraPoints: string[] };
  left: Record<BcPairField, string> & { extraPoints: string[] };
}

export interface BcMeasurementParts {
  whole: string;
  eighth: BcEighthOption;
}

function normalizeBcScoreType(type: BcScoreType | string | null | undefined): BcScoreType {
  return (BC_SCORE_TYPES.find((candidate) => candidate === type) || 'typical_whitetail_unofficial') as BcScoreType;
}

export function getVisibleBcGFields(type: BcScoreType | string | null | undefined): readonly BcGField[] {
  const normalizedType = normalizeBcScoreType(type);
  if (normalizedType === 'typical_mule_deer_unofficial' || normalizedType === 'non_typical_mule_deer_unofficial') {
    return BC_MULE_DEER_G_FIELDS;
  }
  return BC_G_FIELDS;
}

export function getVisibleBcPairFields(type: BcScoreType | string | null | undefined): readonly BcPairField[] {
  return ['mainBeam', ...getVisibleBcGFields(type), ...BC_H_FIELDS];
}

export function bcScoreTypeSupportsExtraNormalPoints(type: BcScoreType | string | null | undefined): boolean {
  const normalizedType = normalizeBcScoreType(type);
  return BC_SCORE_TYPES.includes(normalizedType);
}

function bcScoreTypeCountsExtraPointsAsNormal(type: BcScoreType | string | null | undefined): boolean {
  return normalizeBcScoreType(type) === 'typical_whitetail_unofficial';
}

function bcScoreTypeCountsExtraPointsAsAbnormal(type: BcScoreType | string | null | undefined): boolean {
  const normalizedType = normalizeBcScoreType(type);
  return (
    normalizedType === 'non_typical_whitetail_unofficial' ||
    normalizedType === 'typical_mule_deer_unofficial' ||
    normalizedType === 'non_typical_mule_deer_unofficial'
  );
}

export function isNonTypicalBcScoreType(type: BcScoreType | string | null | undefined): boolean {
  const normalizedType = normalizeBcScoreType(type);
  return (
    normalizedType === 'non_typical_whitetail_unofficial' ||
    normalizedType === 'non_typical_mule_deer_unofficial'
  );
}

function roundMeasurement(value: number | null): number | null {
  if (value === null || value === undefined) {
    return null;
  }
  return Math.round(value * 1000) / 1000;
}

function buildEmptySide(): Record<BcPairField, string> & { extraPoints: string[] } {
  return {
    mainBeam: '',
    g1: '',
    g2: '',
    g3: '',
    g4: '',
    g5: '',
    g6: '',
    g7: '',
    h1: '',
    h2: '',
    h3: '',
    h4: '',
    extraPoints: [],
  };
}

export function createEmptyBcScoreFormState(): BcScoreFormState {
  return {
    type: 'typical_whitetail_unofficial',
    disclaimerAccepted: false,
    pointsSummary: {
      rightPointsCount: '',
      leftPointsCount: '',
      tipToTipSpread: '',
      greatestSpread: '',
    },
    spread: {
      insideSpreadOfMainBeams: '',
    },
    abnormalPoints: {
      right: [],
      left: [],
    },
    right: buildEmptySide(),
    left: buildEmptySide(),
  };
}

function formatFieldValue(value: number | null | undefined): string {
  return value === null || value === undefined ? '' : String(value);
}

export function bcScoreRecordToFormState(score?: BcScoreRecord | null): BcScoreFormState {
  if (!score) {
    return createEmptyBcScoreFormState();
  }
  const form = createEmptyBcScoreFormState();
  form.type = score.type || 'typical_whitetail_unofficial';
  form.disclaimerAccepted = !!score.disclaimerAccepted;
  form.pointsSummary.rightPointsCount = formatFieldValue(score.pointsSummary.rightPointsCount);
  form.pointsSummary.leftPointsCount = formatFieldValue(score.pointsSummary.leftPointsCount);
  form.pointsSummary.tipToTipSpread = formatFieldValue(score.pointsSummary.tipToTipSpread);
  form.pointsSummary.greatestSpread = formatFieldValue(score.pointsSummary.greatestSpread);
  form.spread.insideSpreadOfMainBeams = formatFieldValue(score.spread.insideSpreadOfMainBeams);
  form.abnormalPoints.right = (score.abnormalPoints.right || []).map(formatFieldValue);
  form.abnormalPoints.left = (score.abnormalPoints.left || []).map(formatFieldValue);
  form.right.mainBeam = formatFieldValue(score.right.mainBeam);
  form.left.mainBeam = formatFieldValue(score.left.mainBeam);
  BC_G_FIELDS.forEach((field) => {
    form.right[field] = formatFieldValue(score.right[field]);
    form.left[field] = formatFieldValue(score.left[field]);
  });
  BC_H_FIELDS.forEach((field) => {
    form.right[field] = formatFieldValue(score.right[field]);
    form.left[field] = formatFieldValue(score.left[field]);
  });
  form.right.extraPoints = (score.right.extraPoints || []).map(formatFieldValue);
  form.left.extraPoints = (score.left.extraPoints || []).map(formatFieldValue);
  return form;
}

export function normalizeMeasurementInput(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined) {
    return null;
  }
  if (typeof value === 'number') {
    return value >= 0 ? roundMeasurement(value) : null;
  }
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const normalizedText = trimmed.replace(/(?<=\d)-(?=\d)/g, ' ');
  const fractionMatch = normalizedText.match(FRACTION_PATTERN);
  if (fractionMatch?.groups) {
    const whole = Number.parseInt(fractionMatch.groups.whole || '0', 10);
    const numerator = Number.parseInt(fractionMatch.groups.num, 10);
    const denominator = Number.parseInt(fractionMatch.groups.den, 10);
    if (!denominator) {
      return null;
    }
    return roundMeasurement(whole + numerator / denominator);
  }
  const parsed = Number(normalizedText);
  return Number.isFinite(parsed) && parsed >= 0 ? roundMeasurement(parsed) : null;
}

export function splitMeasurementInput(value: string | number | null | undefined): BcMeasurementParts {
  const normalized = normalizeMeasurementInput(value);
  if (normalized === null) {
    return { whole: '', eighth: '0/8' };
  }
  let whole = Math.floor(normalized);
  let eighthIndex = Math.round((normalized - whole) * 8);
  if (eighthIndex >= 8) {
    whole += 1;
    eighthIndex = 0;
  }
  return {
    whole: String(whole),
    eighth: `${eighthIndex}/8` as BcEighthOption,
  };
}

export function buildMeasurementInput(whole: string, eighth: BcEighthOption): string {
  const sanitizedWhole = whole.replace(/[^\d]/g, '');
  if (!sanitizedWhole) {
    return '';
  }
  const wholeNumber = Number.parseInt(sanitizedWhole, 10);
  const eighthIndex = Number.parseInt(eighth.split('/')[0], 10) || 0;
  return eighthIndex === 0 ? String(wholeNumber) : `${wholeNumber} ${eighthIndex}/8`;
}

export function formatInchesToEighths(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return '—';
  }
  const totalEighths = Math.round(Number(value) * 8);
  const whole = Math.floor(totalEighths / 8);
  const eighths = totalEighths % 8;
  return eighths === 0 ? String(whole) : `${whole} ${eighths}/8`;
}

function normalizePointsCount(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const parsed = Number.parseInt(trimmed, 10);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : null;
}

function normalizeSide(
  side: Record<BcPairField, string> & { extraPoints: string[] },
  scoreType: BcScoreType
): BcSideMeasurements {
  const visibleGFields = new Set(getVisibleBcGFields(scoreType));
  const includeExtraPoints = bcScoreTypeSupportsExtraNormalPoints(scoreType);
  return {
    mainBeam: normalizeMeasurementInput(side.mainBeam),
    g1: visibleGFields.has('g1') ? normalizeMeasurementInput(side.g1) : null,
    g2: visibleGFields.has('g2') ? normalizeMeasurementInput(side.g2) : null,
    g3: visibleGFields.has('g3') ? normalizeMeasurementInput(side.g3) : null,
    g4: visibleGFields.has('g4') ? normalizeMeasurementInput(side.g4) : null,
    g5: visibleGFields.has('g5') ? normalizeMeasurementInput(side.g5) : null,
    g6: visibleGFields.has('g6') ? normalizeMeasurementInput(side.g6) : null,
    g7: visibleGFields.has('g7') ? normalizeMeasurementInput(side.g7) : null,
    h1: normalizeMeasurementInput(side.h1),
    h2: normalizeMeasurementInput(side.h2),
    h3: normalizeMeasurementInput(side.h3),
    h4: normalizeMeasurementInput(side.h4),
    extraPoints: includeExtraPoints
      ? side.extraPoints
          .map((value) => normalizeMeasurementInput(value))
          .filter((value): value is number => value !== null)
      : [],
  };
}

export function formStateToBcScoreEntry(form: BcScoreFormState): BcScoreEntryInput {
  return {
    type: form.type,
    disclaimerAccepted: form.disclaimerAccepted,
    pointsSummary: {
      rightPointsCount: normalizePointsCount(form.pointsSummary.rightPointsCount),
      leftPointsCount: normalizePointsCount(form.pointsSummary.leftPointsCount),
      tipToTipSpread: normalizeMeasurementInput(form.pointsSummary.tipToTipSpread),
      greatestSpread: normalizeMeasurementInput(form.pointsSummary.greatestSpread),
    },
    spread: {
      insideSpreadOfMainBeams: normalizeMeasurementInput(form.spread.insideSpreadOfMainBeams),
    },
    abnormalPoints: {
      right: form.abnormalPoints.right
        .map((value) => normalizeMeasurementInput(value))
        .filter((value): value is number => value !== null),
      left: form.abnormalPoints.left
        .map((value) => normalizeMeasurementInput(value))
        .filter((value): value is number => value !== null),
    },
    right: normalizeSide(form.right, form.type),
    left: normalizeSide(form.left, form.type),
  };
}

export function getBcScoreTypeLabel(type: BcScoreType | string | null | undefined): string {
  return (
    BC_SCORE_TYPE_OPTIONS.find((option) => option.type === type)?.label ||
    'Typical Whitetail Deer'
  );
}

export function isBcScoreTypeImplemented(type: BcScoreType | string | null | undefined): boolean {
  return !!BC_SCORE_TYPE_OPTIONS.find((option) => option.type === type)?.implemented;
}

export function isBcScoreTypeCompatibleWithScan(
  type: BcScoreType | string | null | undefined,
  deerType: string | null | undefined,
  deerSex: string | null | undefined,
  harvestConfirmed: boolean | null | undefined
): boolean {
  const option = BC_SCORE_TYPE_OPTIONS.find((candidate) => candidate.type === type);
  return !!option && !!harvestConfirmed && deerSex === 'Buck' && deerType === option.deerType;
}

export function calculateSpreadCredit(entry: BcScoreEntryInput): number | null {
  const insideSpread = entry.spread.insideSpreadOfMainBeams;
  const longerBeam = Math.max(entry.right.mainBeam || 0, entry.left.mainBeam || 0);
  if (insideSpread === null || insideSpread === undefined || (!entry.right.mainBeam && !entry.left.mainBeam)) {
    return null;
  }
  return roundMeasurement(Math.min(insideSpread, longerBeam));
}

function sideTotal(side: BcSideMeasurements, scoreType: BcScoreType | string | null | undefined): number {
  let total = side.mainBeam || 0;
  getVisibleBcGFields(scoreType).forEach((field) => {
    total += side[field] || 0;
  });
  BC_H_FIELDS.forEach((field) => {
    total += side[field] || 0;
  });
  if (bcScoreTypeCountsExtraPointsAsNormal(scoreType)) {
    (side.extraPoints || []).forEach((value) => {
      total += value || 0;
    });
  }
  return Math.round(total * 1000) / 1000;
}

function getCombinedAbnormalPoints(
  entry: BcScoreEntryInput,
  sideName: 'right' | 'left'
): number[] {
  const values = [...(entry.abnormalPoints[sideName] || [])];
  if (bcScoreTypeCountsExtraPointsAsAbnormal(entry.type)) {
    values.push(...(entry[sideName].extraPoints || []));
  }
  return values;
}

export function calculateTypicalWhitetailColumnTotals(entry: BcScoreEntryInput): {
  rightTotal: number | null;
  leftTotal: number | null;
} {
  const visibleGFields = getVisibleBcGFields(entry.type);
  const includeExtraPoints = bcScoreTypeCountsExtraPointsAsNormal(entry.type);
  const hasAnyScore =
    entry.right.mainBeam !== null ||
    entry.left.mainBeam !== null ||
    visibleGFields.some((field) => entry.right[field] !== null || entry.left[field] !== null) ||
    BC_H_FIELDS.some((field) => entry.right[field] !== null || entry.left[field] !== null) ||
    (includeExtraPoints && ((entry.right.extraPoints || []).length > 0 || (entry.left.extraPoints || []).length > 0));
  if (!hasAnyScore) {
    return { rightTotal: null, leftTotal: null };
  }
  return {
    rightTotal: sideTotal(entry.right, entry.type),
    leftTotal: sideTotal(entry.left, entry.type),
  };
}

export function calculateTypicalWhitetailDeductions(entry: BcScoreEntryInput): {
  pairedDifferences: Record<string, number | null>;
  pairedDifferencesTotal: number | null;
  abnormalDeductionTotal: number | null;
  deductionsTotal: number | null;
} {
  const pairedDifferences: Record<string, number | null> = {};
  let pairedTotal = 0;
  const visiblePairFields = getVisibleBcPairFields(entry.type);
  const includeExtraPoints = bcScoreTypeCountsExtraPointsAsNormal(entry.type);

  visiblePairFields.forEach((field) => {
    const rightValue = entry.right[field];
    const leftValue = entry.left[field];
    if (rightValue === null && leftValue === null) {
      pairedDifferences[field] = null;
      return;
    }
    const difference = Math.abs((rightValue || 0) - (leftValue || 0));
    pairedDifferences[field] = roundMeasurement(difference);
    pairedTotal += difference;
  });

  if (includeExtraPoints) {
    const extraPointCount = Math.max(entry.right.extraPoints?.length || 0, entry.left.extraPoints?.length || 0);
    for (let index = 0; index < extraPointCount; index += 1) {
      const fieldName = `g${8 + index}`;
      const rightValue = entry.right.extraPoints?.[index] ?? null;
      const leftValue = entry.left.extraPoints?.[index] ?? null;
      if (rightValue === null && leftValue === null) {
        pairedDifferences[fieldName] = null;
        continue;
      }
      const difference = Math.abs((rightValue || 0) - (leftValue || 0));
      pairedDifferences[fieldName] = roundMeasurement(difference);
      pairedTotal += difference;
    }
  }

  const abnormalDeductionTotal = roundMeasurement(
    getCombinedAbnormalPoints(entry, 'right').reduce((total, value) => total + value, 0) +
      getCombinedAbnormalPoints(entry, 'left').reduce((total, value) => total + value, 0)
  );
  const isNonTypical = isNonTypicalBcScoreType(entry.type);

  return {
    pairedDifferences,
    pairedDifferencesTotal: roundMeasurement(pairedTotal),
    abnormalDeductionTotal,
    deductionsTotal: roundMeasurement(pairedTotal + (isNonTypical ? 0 : abnormalDeductionTotal || 0)),
  };
}

function calculateSubtotalOne(
  spreadCredit: number | null,
  columns: { rightTotal: number | null; leftTotal: number | null }
): number | null {
  if (spreadCredit === null && columns.rightTotal === null && columns.leftTotal === null) {
    return null;
  }
  return roundMeasurement((spreadCredit || 0) + (columns.rightTotal || 0) + (columns.leftTotal || 0));
}

function calculateSubtotalTwo(
  subtotalOne: number | null,
  pairedDifferencesTotal: number | null
): number | null {
  if (subtotalOne === null) {
    return null;
  }
  return roundMeasurement((subtotalOne || 0) - (pairedDifferencesTotal || 0));
}

function calculateGrossScore(
  scoreType: BcScoreType | string | null | undefined,
  subtotalOne: number | null,
  abnormalTotal: number | null
): number | null {
  if (subtotalOne === null) {
    return null;
  }
  if (isNonTypicalBcScoreType(scoreType)) {
    return roundMeasurement((subtotalOne || 0) + (abnormalTotal || 0));
  }
  return roundMeasurement(subtotalOne);
}

export function calculateTypicalWhitetailFinalScore(entry: BcScoreEntryInput): number | null {
  const spreadCredit = calculateSpreadCredit(entry);
  const columns = calculateTypicalWhitetailColumnTotals(entry);
  const deductions = calculateTypicalWhitetailDeductions(entry);
  const subtotalOne = calculateSubtotalOne(spreadCredit, columns);
  const subtotalTwo = calculateSubtotalTwo(subtotalOne, deductions.pairedDifferencesTotal);
  if (subtotalOne === null || subtotalTwo === null) {
    return null;
  }
  if (isNonTypicalBcScoreType(entry.type)) {
    return roundMeasurement(Math.max(0, (subtotalTwo || 0) + (deductions.abnormalDeductionTotal || 0)));
  }
  return roundMeasurement(Math.max(0, (subtotalOne || 0) - (deductions.deductionsTotal || 0)));
}

function highestFilledIndex(side: BcSideMeasurements, fields: readonly string[], trailingCount = 0): number {
  let highest = 0;
  fields.forEach((field, index) => {
    if (side[field as BcPairField] !== null) {
      highest = index + 1;
    }
  });
  if (trailingCount > 0) {
    highest = fields.length + trailingCount;
  }
  return highest;
}

function hasGapBeforeLaterValue(side: BcSideMeasurements, fields: readonly string[], trailingCount = 0): boolean {
  const highest = highestFilledIndex(side, fields, trailingCount);
  if (highest <= 1) {
    return false;
  }
  return fields.slice(0, highest - 1).some((field) => side[field as BcPairField] === null);
}

function requiredHCount(
  side: BcSideMeasurements,
  type: BcScoreType | string | null | undefined
): number {
  const extraCount = bcScoreTypeCountsExtraPointsAsNormal(type) ? side.extraPoints?.length || 0 : 0;
  return Math.min(4, highestFilledIndex(side, getVisibleBcGFields(type), extraCount));
}

export function validateBcScoreEntry(entry: BcScoreEntryInput): BcValidationWarning[] {
  const warnings: BcValidationWarning[] = [];
  const spreadCredit = calculateSpreadCredit(entry);
  const longerBeam = Math.max(entry.right.mainBeam || 0, entry.left.mainBeam || 0);
  const visibleGFields = getVisibleBcGFields(entry.type);
  const includeExtraPoints = bcScoreTypeCountsExtraPointsAsNormal(entry.type);

  if (
    spreadCredit !== null &&
    entry.spread.insideSpreadOfMainBeams !== null &&
    longerBeam > 0 &&
    entry.spread.insideSpreadOfMainBeams > longerBeam
  ) {
    warnings.push({
      code: 'spread_credit_capped',
      message: 'Inside spread is larger than the longer main beam, so spread credit will be capped.',
    });
  }

  const deductions = calculateTypicalWhitetailDeductions(entry);
  const pairFieldNames = [
    ...getVisibleBcPairFields(entry.type),
    ...(
      includeExtraPoints
        ? Array.from(
            { length: Math.max(entry.right.extraPoints?.length || 0, entry.left.extraPoints?.length || 0) },
            (_, index) => `g${8 + index}`
          )
        : []
    ),
  ];
  const largeDifference = pairFieldNames.find((field) => (deductions.pairedDifferences[field] || 0) >= ASYMMETRY_WARNING_THRESHOLD);
  if (largeDifference) {
    warnings.push({
      code: 'large_left_right_difference',
      message: `${BC_PAIR_LABELS[largeDifference as BcPairField] || `G-${largeDifference.replace('g', '')}`} differs sharply from side to side. Recheck for entry mistakes.`,
    });
  }

  (
    [
      ['right', entry.right],
      ['left', entry.left],
    ] as const
  ).forEach(([sideName, side]) => {
    const extraCount = includeExtraPoints ? side.extraPoints?.length || 0 : 0;
    if (hasGapBeforeLaterValue(side, visibleGFields, extraCount)) {
      warnings.push({
        code: `${sideName}_non_contiguous_points`,
        message: `${sideName[0].toUpperCase()}${sideName.slice(1)} antler point lengths have a gap before a later point entry.`,
      });
    }
    if (hasGapBeforeLaterValue(side, BC_H_FIELDS)) {
      warnings.push({
        code: `${sideName}_non_contiguous_circumferences`,
        message: `${sideName[0].toUpperCase()}${sideName.slice(1)} circumference entries have a gap before a later circumference entry.`,
      });
    }
    const missingRequiredH = BC_H_FIELDS.slice(0, requiredHCount(side, entry.type)).some((field) => side[field] === null);
    if (missingRequiredH) {
      warnings.push({
        code: `${sideName}_missing_circumferences`,
        message: `${sideName[0].toUpperCase()}${sideName.slice(1)} circumference measurements are missing while later point lengths are present.`,
      });
    }
  });

  return warnings;
}

export function isBcScoreComplete(entry: BcScoreEntryInput): boolean {
  const visibleGFields = getVisibleBcGFields(entry.type);
  const includeExtraPoints = bcScoreTypeCountsExtraPointsAsNormal(entry.type);
  const requiredBaseValues = [
    entry.disclaimerAccepted,
    entry.pointsSummary.rightPointsCount,
    entry.pointsSummary.leftPointsCount,
    entry.pointsSummary.tipToTipSpread,
    entry.pointsSummary.greatestSpread,
    entry.spread.insideSpreadOfMainBeams,
    entry.right.mainBeam,
    entry.left.mainBeam,
  ];

  if (
    !entry.disclaimerAccepted ||
    requiredBaseValues.some((value) => value === null || value === undefined || value === false)
  ) {
    return false;
  }

  if (
    hasGapBeforeLaterValue(entry.right, visibleGFields, includeExtraPoints ? entry.right.extraPoints?.length || 0 : 0) ||
    hasGapBeforeLaterValue(entry.left, visibleGFields, includeExtraPoints ? entry.left.extraPoints?.length || 0 : 0)
  ) {
    return false;
  }
  if (hasGapBeforeLaterValue(entry.right, BC_H_FIELDS) || hasGapBeforeLaterValue(entry.left, BC_H_FIELDS)) {
    return false;
  }

  const perSideChecks = (
    [
      ['right', entry.right, entry.pointsSummary.rightPointsCount, getCombinedAbnormalPoints(entry, 'right').length > 0],
      ['left', entry.left, entry.pointsSummary.leftPointsCount, getCombinedAbnormalPoints(entry, 'left').length > 0],
    ] as const
  );

  return perSideChecks.every(([, side, pointsCount, hasAbnormalPoints]) => {
    const requiredHs = BC_H_FIELDS.slice(0, requiredHCount(side, entry.type));
    if (requiredHs.some((field) => side[field] === null)) {
      return false;
    }
    const hasAnyNormalMeasurement =
      visibleGFields.some((field) => side[field] !== null) ||
      (includeExtraPoints && (side.extraPoints || []).length > 0);
    if ((pointsCount || 0) > 1 && !hasAnyNormalMeasurement && !hasAbnormalPoints) {
      return false;
    }
    return true;
  });
}

export function buildBcScorePreview(entry: BcScoreEntryInput): BcScoreRecord {
  const spreadCredit = calculateSpreadCredit(entry);
  const columns = calculateTypicalWhitetailColumnTotals(entry);
  const deductions = calculateTypicalWhitetailDeductions(entry);
  const subtotalOne = calculateSubtotalOne(spreadCredit, columns);
  const subtotalTwo = calculateSubtotalTwo(subtotalOne, deductions.pairedDifferencesTotal);
  const finalScore = calculateTypicalWhitetailFinalScore(entry);
  const grossScore = calculateGrossScore(entry.type, subtotalOne, deductions.abnormalDeductionTotal);
  const rightAbnormalPoints = getCombinedAbnormalPoints(entry, 'right');
  const leftAbnormalPoints = getCombinedAbnormalPoints(entry, 'left');
  const timestamp = new Date().toISOString();

  return {
    type: entry.type || 'typical_whitetail_unofficial',
    status: isBcScoreComplete(entry) ? 'complete' : 'draft',
    enteredManually: true,
    disclaimerAccepted: entry.disclaimerAccepted,
    pointsSummary: {
      ...entry.pointsSummary,
    },
    spread: {
      insideSpreadOfMainBeams: entry.spread.insideSpreadOfMainBeams,
      spreadCredit,
    },
    abnormalPoints: {
      right: entry.abnormalPoints.right,
      left: entry.abnormalPoints.left,
      rightTotalLength: roundMeasurement(rightAbnormalPoints.reduce((total, value) => total + value, 0)),
      leftTotalLength: roundMeasurement(leftAbnormalPoints.reduce((total, value) => total + value, 0)),
      totalLength: roundMeasurement(
        rightAbnormalPoints.reduce((total, value) => total + value, 0) +
          leftAbnormalPoints.reduce((total, value) => total + value, 0)
      ),
    },
    right: entry.right,
    left: entry.left,
    computed: {
      rightTotal: columns.rightTotal,
      leftTotal: columns.leftTotal,
      subtotalOne,
      pairedDifferencesTotal: deductions.pairedDifferencesTotal,
      abnormalDeductionTotal: deductions.abnormalDeductionTotal,
      deductionsTotal: deductions.deductionsTotal,
      subtotalTwo,
      grossScore,
      finalScore,
    },
    differences: deductions.pairedDifferences,
    warnings: validateBcScoreEntry(entry),
    calculatedAt: timestamp,
    updatedAt: timestamp,
  };
}
