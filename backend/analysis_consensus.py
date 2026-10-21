from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple


def _normalize_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _round_to_half_year(value: float) -> float:
    return round(value * 2) / 2.0


def _majority_value(values: Sequence[Any], default: Any = None) -> Any:
    counts: Dict[Any, int] = {}
    first_seen: Dict[Any, int] = {}
    for index, value in enumerate(values):
        if value is None or value == "":
            continue
        counts[value] = counts.get(value, 0) + 1
        first_seen.setdefault(value, index)
    if not counts:
        return default
    best = max(counts.items(), key=lambda item: (item[1], -first_seen[item[0]]))
    return best[0]


def _majority_with_counts(values: Sequence[Any]) -> Tuple[Any, Dict[str, int]]:
    counts: Dict[str, int] = {}
    ordered_values: List[Any] = []
    for value in values:
        if value is None or value == "":
            continue
        key = str(value)
        counts[key] = counts.get(key, 0) + 1
        ordered_values.append(value)
    return _majority_value(ordered_values), counts


def _majority_bool(values: Sequence[bool], default: bool = False) -> bool:
    trues = sum(1 for value in values if value)
    falses = sum(1 for value in values if not value)
    if trues == falses:
        return default
    return trues > falses


def build_consensus_age_range(age_values: Sequence[float]) -> Optional[str]:
    cleaned = sorted(_round_to_half_year(value) for value in age_values if value is not None)
    if not cleaned:
        return None
    minimum = cleaned[0]
    maximum = cleaned[-1]
    if minimum == maximum:
        return None
    if maximum >= 6.5:
        return f"{minimum:.1f}-6.5+"
    return f"{minimum:.1f}-{maximum:.1f}"


def should_trigger_selective_consensus(
    analysis: Dict[str, Any],
    *,
    enabled: bool,
    max_age_confidence: int,
    max_recommendation_confidence: int,
    harvest_threshold: float = 3.5,
    harvest_window: float = 0.5,
) -> bool:
    if not enabled:
        return False
    if not analysis.get("is_valid_deer", False):
        return False
    if analysis.get("age_estimation_allowed") is False:
        return False

    deer_age = _normalize_float(analysis.get("deer_age"))
    if deer_age is None:
        return False

    age_confidence = _normalize_int(
        analysis.get("raw_age_confidence")
        if analysis.get("raw_age_confidence") is not None
        else analysis.get("confidence")
    )
    recommendation_confidence = _normalize_int(
        analysis.get("raw_recommendation_confidence")
        if analysis.get("raw_recommendation_confidence") is not None
        else analysis.get("confidence")
    )

    if age_confidence is not None and age_confidence <= max_age_confidence:
        return True
    if recommendation_confidence is not None and recommendation_confidence <= max_recommendation_confidence:
        return True

    # Borderline harvest decisions get a slightly looser trigger.
    near_harvest_boundary = abs(deer_age - harvest_threshold) <= max(0.0, harvest_window)
    if near_harvest_boundary and age_confidence is not None:
        return age_confidence <= max(max_age_confidence, max_recommendation_confidence) + 10

    return False


def merge_consensus_analyses(
    analyses: Sequence[Dict[str, Any]],
    *,
    age_spread_penalty_per_half_year: int = 8,
    disagreement_penalty: int = 12,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    if not analyses:
        return {}, {"applied": False, "reason": "no_analyses"}

    valid_analyses = [analysis for analysis in analyses if analysis.get("is_valid_deer", False)]
    if not valid_analyses:
        return dict(analyses[0]), {"applied": False, "reason": "no_valid_analyses"}

    allowed_votes = [
        analysis.get("age_estimation_allowed") is not False and _normalize_float(analysis.get("deer_age")) is not None
        for analysis in valid_analyses
    ]
    majority_allowed = _majority_bool(allowed_votes, default=allowed_votes[0] if allowed_votes else False)

    allowed_analyses = [
        analysis
        for analysis in valid_analyses
        if analysis.get("age_estimation_allowed") is not False and _normalize_float(analysis.get("deer_age")) is not None
    ]
    age_values = [
        _normalize_float(analysis.get("deer_age"))
        for analysis in allowed_analyses
    ]
    age_values = [value for value in age_values if value is not None]

    # Collect alternate_age values to use as supporting evidence
    alternate_age_values = [
        _normalize_float(analysis.get("alternate_age"))
        for analysis in allowed_analyses
    ]
    alternate_age_values = [value for value in alternate_age_values if value is not None]

    # Compute initial consensus from primary ages
    consensus_age = _round_to_half_year(sorted(age_values)[len(age_values) // 2]) if age_values else None

    # Leverage alternate ages: if alternate ages cluster around a different value than
    # primary ages, and the spread is large, use alternate ages as tie-breakers.
    # Specifically: build a combined vote pool where each pass contributes its primary age
    # and, if its alternate_age is closer to the primary consensus than its own primary age,
    # that alternate also gets a weighted vote.
    if consensus_age is not None and len(age_values) >= 2 and alternate_age_values:
        # Count how many alternate_ages support the consensus (within 0.5 year)
        alternate_support_count = sum(
            1 for alt in alternate_age_values
            if abs(alt - consensus_age) <= 0.5
        )
        # Count how many primary ages disagree with consensus (more than 0.5 year away)
        primary_disagree_count = sum(
            1 for age in age_values
            if abs(age - consensus_age) > 0.5
        )

        # If alternates support the consensus more than primaries disagree, boost confidence.
        # Build an augmented age pool: primary ages + alternate ages that agree with consensus.
        if alternate_support_count > 0 and primary_disagree_count > 0:
            augmented_ages = list(age_values)
            for analysis in allowed_analyses:
                alt = _normalize_float(analysis.get("alternate_age"))
                primary = _normalize_float(analysis.get("deer_age"))
                if alt is not None and primary is not None:
                    # Include alternate if it's closer to consensus than the primary
                    if abs(alt - consensus_age) < abs(primary - consensus_age):
                        augmented_ages.append(alt)
            # Recompute consensus from augmented pool
            augmented_ages_sorted = sorted(augmented_ages)
            consensus_age = _round_to_half_year(
                augmented_ages_sorted[len(augmented_ages_sorted) // 2]
            )

    representative = valid_analyses[0]
    if consensus_age is not None:
        representative = min(
            allowed_analyses or valid_analyses,
            key=lambda analysis: (
                abs((_normalize_float(analysis.get("deer_age")) or consensus_age) - consensus_age),
                -(_normalize_int(analysis.get("raw_age_confidence")) or 0),
            ),
        )

    merged = dict(representative)

    merged["deer_type"] = _majority_value(
        [analysis.get("deer_type") for analysis in valid_analyses],
        default=merged.get("deer_type"),
    )
    merged["deer_sex"] = _majority_value(
        [analysis.get("deer_sex") for analysis in valid_analyses],
        default=merged.get("deer_sex"),
    )
    merged["body_condition"] = _majority_value(
        [analysis.get("body_condition") for analysis in valid_analyses],
        default=merged.get("body_condition"),
    )
    merged["image_quality_bucket"] = _majority_value(
        [analysis.get("image_quality_bucket") for analysis in valid_analyses],
        default=merged.get("image_quality_bucket"),
    )
    merged["posture_bucket"] = _majority_value(
        [analysis.get("posture_bucket") for analysis in valid_analyses],
        default=merged.get("posture_bucket"),
    )

    antler_left = _majority_value(
        [_normalize_int(analysis.get("antler_points_left")) for analysis in valid_analyses],
        default=merged.get("antler_points_left"),
    )
    antler_right = _majority_value(
        [_normalize_int(analysis.get("antler_points_right")) for analysis in valid_analyses],
        default=merged.get("antler_points_right"),
    )
    antler_total = _majority_value(
        [_normalize_int(analysis.get("antler_points")) for analysis in valid_analyses],
        default=merged.get("antler_points"),
    )
    if antler_left is not None and antler_right is not None:
        antler_total = antler_left + antler_right

    merged["antler_points_left"] = antler_left
    merged["antler_points_right"] = antler_right
    merged["antler_points"] = antler_total
    merged["buck_age_class"] = _majority_value(
        [analysis.get("buck_age_class") for analysis in valid_analyses],
        default=merged.get("buck_age_class"),
    )

    cue_counts: Dict[str, int] = {}
    for analysis in valid_analyses:
        for cue in analysis.get("visible_age_cues") or []:
            cue_counts[str(cue)] = cue_counts.get(str(cue), 0) + 1
    minimum_cue_support = max(1, (len(valid_analyses) + 1) // 2)
    merged["visible_age_cues"] = [
        cue
        for cue, count in sorted(cue_counts.items(), key=lambda item: (-item[1], item[0]))
        if count >= minimum_cue_support
    ]

    quality_factors: Dict[str, Any] = {}
    quality_factor_keys = set()
    for analysis in valid_analyses:
        quality_factor_keys.update((analysis.get("quality_factors") or {}).keys())
    for key in quality_factor_keys:
        quality_factors[key] = _majority_value(
            [(analysis.get("quality_factors") or {}).get(key) for analysis in valid_analyses]
        )
    if quality_factors:
        merged["quality_factors"] = quality_factors

    age_conf_samples = [
        _normalize_int(
            analysis.get("raw_age_confidence")
            if analysis.get("raw_age_confidence") is not None
            else analysis.get("confidence")
        )
        for analysis in valid_analyses
    ]
    age_conf_samples = [value for value in age_conf_samples if value is not None]
    rec_conf_samples = [
        _normalize_int(
            analysis.get("raw_recommendation_confidence")
            if analysis.get("raw_recommendation_confidence") is not None
            else analysis.get("confidence")
        )
        for analysis in valid_analyses
    ]
    rec_conf_samples = [value for value in rec_conf_samples if value is not None]

    base_age_confidence = sorted(age_conf_samples)[len(age_conf_samples) // 2] if age_conf_samples else None
    base_recommendation_confidence = sorted(rec_conf_samples)[len(rec_conf_samples) // 2] if rec_conf_samples else None

    recommendation_values = [
        str(analysis.get("recommendation")).upper()
        for analysis in allowed_analyses
        if analysis.get("recommendation")
    ]
    consensus_recommendation, recommendation_counts = _majority_with_counts(recommendation_values)

    age_spread = round(max(age_values) - min(age_values), 1) if len(age_values) >= 2 else 0.0
    allowed_true_count = sum(1 for value in allowed_votes if value)
    allowed_false_count = len(allowed_votes) - allowed_true_count
    allowed_agreement = (
        max(allowed_true_count, allowed_false_count) / len(allowed_votes)
        if allowed_votes
        else 1.0
    )
    recommendation_agreement = (
        max(recommendation_counts.values()) / len(recommendation_values)
        if recommendation_values and recommendation_counts
        else 1.0
    )

    penalty = 0
    if age_spread > 0:
        penalty += int(round((age_spread / 0.5) * age_spread_penalty_per_half_year))
    if recommendation_values:
        penalty += int(round((1.0 - recommendation_agreement) * disagreement_penalty))
    if allowed_votes:
        penalty += int(round((1.0 - allowed_agreement) * disagreement_penalty))

    # Alternate-age consensus bonus: reduce penalty when alternate ages from
    # disagreeing passes actually support the final consensus age.
    if consensus_age is not None and alternate_age_values and penalty > 0:
        supporting_alternates = sum(
            1 for alt in alternate_age_values
            if abs(alt - consensus_age) <= 0.5
        )
        if supporting_alternates > 0:
            # Each supporting alternate reduces penalty by up to 4 points
            alt_bonus = min(penalty, supporting_alternates * 4)
            penalty = max(0, penalty - alt_bonus)

    adjusted_age_confidence = (
        max(0, min(100, base_age_confidence - penalty))
        if base_age_confidence is not None
        else None
    )
    adjusted_recommendation_confidence = (
        max(0, min(100, base_recommendation_confidence - penalty))
        if base_recommendation_confidence is not None
        else None
    )

    if majority_allowed and consensus_age is not None:
        merged["age_estimation_allowed"] = True
        merged["deer_age"] = consensus_age
        merged["retake_reason"] = None
        merged["recommendation"] = consensus_recommendation
    else:
        merged["age_estimation_allowed"] = False
        merged["deer_age"] = None
        merged["recommendation"] = None
        merged["retake_reason"] = _majority_value(
            [analysis.get("retake_reason") for analysis in valid_analyses],
            default=merged.get("retake_reason"),
        )
        adjusted_age_confidence = 0
        adjusted_recommendation_confidence = 0

    merged["raw_age_confidence"] = adjusted_age_confidence
    merged["raw_recommendation_confidence"] = adjusted_recommendation_confidence
    merged["confidence"] = adjusted_recommendation_confidence or adjusted_age_confidence or 0

    consensus_metadata = {
        "applied": True,
        "passes_requested": len(analyses),
        "passes_used": len(valid_analyses),
        "invalid_passes": len(analyses) - len(valid_analyses),
        "age_values": age_values,
        "alternate_age_values": alternate_age_values,
        "age_spread": age_spread,
        "age_range": build_consensus_age_range(age_values),
        "recommendation_votes": recommendation_counts,
        "allowed_votes": {
            "true": allowed_true_count,
            "false": allowed_false_count,
        },
        "confidence_penalty": penalty,
    }
    merged["consensus"] = consensus_metadata

    return merged, consensus_metadata
