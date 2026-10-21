// Shared age-estimate presentation: best estimate, plausible range, and what the range means.

export type AgeFields = {
  deer_age?: number | null;
  age_lower?: number | null;
  age_upper?: number | null;
  age_upper_open?: boolean | null;
  age_range?: string | null;
  range_status?: string | null;
  range_coverage_confidence?: number | null;
  recommendation_status?: string | null;
  harvest_age_threshold?: number | null;
};

export type AgeDescription = {
  best: string | null;        // "3.5 yrs"
  range: string | null;       // "3.5–4.5 yrs" | "5.5+ yrs" | null (point estimate)
  rangeLabel: string | null;  // what the range means
  calibrated: boolean;
  recommendationUncertain: boolean;
};

const fmt = (n: number) => (Number.isInteger(n) ? `${n}.0` : `${n}`);

export function describeAge(s: AgeFields): AgeDescription {
  const age = s.deer_age;
  const recommendationUncertain = s.recommendation_status === 'uncertain_range_crosses_threshold';
  if (age === null || age === undefined || age === 0) {
    return { best: null, range: null, rangeLabel: null, calibrated: false, recommendationUncertain: false };
  }
  const best = `${fmt(age)} yrs`;
  // New scans: evidence-derived bounds
  if (s.age_lower !== null && s.age_lower !== undefined) {
    const calibrated = s.range_status === 'calibrated' && typeof s.range_coverage_confidence === 'number';
    let range: string | null = null;
    if (s.age_upper_open) range = `${fmt(s.age_lower)}+ yrs`;
    else if (s.age_upper !== null && s.age_upper !== undefined && s.age_upper !== s.age_lower) {
      range = `${fmt(s.age_lower)}–${fmt(s.age_upper)} yrs`;
    }
    const rangeLabel = range
      ? calibrated
        ? `Range covers the true age ${s.range_coverage_confidence}% of the time (validated)`
        : 'Plausible range · not a calibrated probability'
      : null;
    return { best, range, rangeLabel, calibrated, recommendationUncertain };
  }
  // Older scans: age_range was a fixed class bin, never a validated interval
  if (s.age_range && s.age_range !== String(age)) {
    return {
      best,
      range: `${s.age_range} yrs`,
      rangeLabel: 'Age class from an older scan (not a validated range)',
      calibrated: false,
      recommendationUncertain,
    };
  }
  return { best, range: null, rangeLabel: null, calibrated: false, recommendationUncertain };
}

export const DEFAULT_HARVEST_AGE = 3.5;
export const HARVEST_AGE_OPTIONS = [2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 6.5];

export const formatHarvestAge = (age?: number | null): string =>
  `${(age ?? DEFAULT_HARVEST_AGE).toFixed(1)}+`;

export const uncertainRecommendationText = (harvestAge?: number | null): string =>
  `The plausible age range spans your ${(harvestAge ?? DEFAULT_HARVEST_AGE).toFixed(1)}-year harvest age, so the age-based call is uncertain.`;
