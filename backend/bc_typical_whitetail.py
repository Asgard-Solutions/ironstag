import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

BC_SCORE_TYPE = "typical_whitetail_unofficial"
BC_SCORE_TYPE_NON_TYPICAL_WHITETAIL = "non_typical_whitetail_unofficial"
BC_SCORE_TYPE_TYPICAL_MULE_DEER = "typical_mule_deer_unofficial"
BC_SCORE_TYPE_NON_TYPICAL_MULE_DEER = "non_typical_mule_deer_unofficial"
ALL_BC_SCORE_TYPES = (
    BC_SCORE_TYPE,
    BC_SCORE_TYPE_NON_TYPICAL_WHITETAIL,
    BC_SCORE_TYPE_TYPICAL_MULE_DEER,
    BC_SCORE_TYPE_NON_TYPICAL_MULE_DEER,
)
SUPPORTED_BC_SCORE_TYPES = (
    BC_SCORE_TYPE,
    BC_SCORE_TYPE_NON_TYPICAL_WHITETAIL,
    BC_SCORE_TYPE_TYPICAL_MULE_DEER,
    BC_SCORE_TYPE_NON_TYPICAL_MULE_DEER,
)
BC_SCORE_TYPE_REQUIRED_DEER_TYPE = {
    BC_SCORE_TYPE: "Whitetail",
    BC_SCORE_TYPE_NON_TYPICAL_WHITETAIL: "Whitetail",
    BC_SCORE_TYPE_TYPICAL_MULE_DEER: "Mule Deer",
    BC_SCORE_TYPE_NON_TYPICAL_MULE_DEER: "Mule Deer",
}
BC_SCORE_TYPE_LABELS = {
    BC_SCORE_TYPE: "Typical Whitetail Deer",
    BC_SCORE_TYPE_NON_TYPICAL_WHITETAIL: "Non-Typical Whitetail Deer",
    BC_SCORE_TYPE_TYPICAL_MULE_DEER: "Typical Mule Deer",
    BC_SCORE_TYPE_NON_TYPICAL_MULE_DEER: "Non-Typical Mule Deer",
}
BC_STATUS_DRAFT = "draft"
BC_STATUS_COMPLETE = "complete"
G_LABELS = ("g1", "g2", "g3", "g4", "g5", "g6", "g7")
MULE_DEER_G_LABELS = ("g1", "g2", "g3", "g4")
H_LABELS = ("h1", "h2", "h3", "h4")
FIXED_PAIR_FIELDS = ("mainBeam",) + G_LABELS + H_LABELS
PAIR_FIELD_LABELS = {
    "mainBeam": "F Main Beam",
    "g1": "G-1",
    "g2": "G-2",
    "g3": "G-3",
    "g4": "G-4",
    "g5": "G-5",
    "g6": "G-6",
    "g7": "G-7",
    "h1": "H-1",
    "h2": "H-2",
    "h3": "H-3",
    "h4": "H-4",
}
ASYMMETRY_WARNING_THRESHOLD = 8.0
FRACTION_PATTERN = re.compile(r"^(?:(?P<whole>\d+)\s+)?(?P<num>\d+)\s*/\s*(?P<den>\d+)$")


def round_measurement(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return round(value, 3)


def normalize_measurement_input(value: Any, *, max_value: float = 999.0) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)
    else:
        text = str(value).strip()
        if not text:
            return None
        normalized_text = re.sub(r"(?<=\d)-(?=\d)", " ", text)
        fraction_match = FRACTION_PATTERN.match(normalized_text)
        if fraction_match:
            whole = int(fraction_match.group("whole") or 0)
            numerator = int(fraction_match.group("num"))
            denominator = int(fraction_match.group("den"))
            if denominator <= 0:
                return None
            number = whole + (numerator / denominator)
        else:
            try:
                number = float(normalized_text)
            except ValueError:
                return None

    if number < 0:
        return None
    return round(min(number, max_value), 3)


def normalize_points_count(value: Any, *, max_value: int = 30) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    if number < 0:
        return None
    return min(number, max_value)


def format_inches_to_eighths(value: Optional[float]) -> str:
    if value is None:
        return "—"
    total_eighths = int(round(float(value) * 8))
    whole = total_eighths // 8
    eighths = total_eighths % 8
    if eighths == 0:
        return str(whole)
    return f"{whole} {eighths}/8"


def normalize_bc_score_type(value: Any) -> Optional[str]:
    if value is None or value == "":
        return None
    cleaned = str(value).strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "typical_whitetail_unofficial": BC_SCORE_TYPE,
        "typical_whitetail": BC_SCORE_TYPE,
        "typical_whitetail_deer": BC_SCORE_TYPE,
        "non_typical_whitetail_unofficial": BC_SCORE_TYPE_NON_TYPICAL_WHITETAIL,
        "non_typical_whitetail": BC_SCORE_TYPE_NON_TYPICAL_WHITETAIL,
        "non_typical_whitetail_deer": BC_SCORE_TYPE_NON_TYPICAL_WHITETAIL,
        "typical_mule_deer_unofficial": BC_SCORE_TYPE_TYPICAL_MULE_DEER,
        "typical_mule_deer": BC_SCORE_TYPE_TYPICAL_MULE_DEER,
        "non_typical_mule_deer_unofficial": BC_SCORE_TYPE_NON_TYPICAL_MULE_DEER,
        "non_typical_mule_deer": BC_SCORE_TYPE_NON_TYPICAL_MULE_DEER,
    }
    return aliases.get(cleaned)


def is_supported_bc_score_type(score_type: Optional[str]) -> bool:
    return bool(score_type in SUPPORTED_BC_SCORE_TYPES)


def get_bc_score_type_label(score_type: Optional[str]) -> str:
    normalized_type = normalize_bc_score_type(score_type) or BC_SCORE_TYPE
    return BC_SCORE_TYPE_LABELS.get(normalized_type, BC_SCORE_TYPE_LABELS[BC_SCORE_TYPE])


def _normalize_scoring_deer_type(value: Any) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip().lower()
    if cleaned in {"whitetail", "white-tailed deer", "white tailed deer", "whitetail deer"}:
        return "Whitetail"
    if cleaned in {"mule deer", "mule"}:
        return "Mule Deer"
    return str(value).strip() or None


def _normalize_scoring_deer_sex(value: Any) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip().lower()
    if cleaned == "buck":
        return "Buck"
    if cleaned == "doe":
        return "Doe"
    if cleaned == "unknown":
        return "Unknown"
    return str(value).strip() or None


def is_harvested_buck_eligible(
    deer_type: Optional[str],
    deer_sex: Optional[str],
    harvest_confirmed: bool,
) -> bool:
    return bool(
        harvest_confirmed
        and _normalize_scoring_deer_sex(deer_sex) == "Buck"
        and _normalize_scoring_deer_type(deer_type) in {"Whitetail", "Mule Deer"}
    )


def is_bc_score_type_allowed_for_scan(
    score_type: Optional[str],
    deer_type: Optional[str],
    deer_sex: Optional[str],
    harvest_confirmed: bool,
) -> bool:
    normalized_type = normalize_bc_score_type(score_type)
    if normalized_type is None:
        return False
    required_deer_type = BC_SCORE_TYPE_REQUIRED_DEER_TYPE.get(normalized_type)
    return bool(
        harvest_confirmed
        and _normalize_scoring_deer_sex(deer_sex) == "Buck"
        and _normalize_scoring_deer_type(deer_type) == required_deer_type
    )


def _active_g_labels(score_type: Optional[str]) -> Tuple[str, ...]:
    normalized_type = normalize_bc_score_type(score_type) or BC_SCORE_TYPE
    if normalized_type in {BC_SCORE_TYPE_TYPICAL_MULE_DEER, BC_SCORE_TYPE_NON_TYPICAL_MULE_DEER}:
        return MULE_DEER_G_LABELS
    return G_LABELS


def _supports_extra_normal_points(score_type: Optional[str]) -> bool:
    normalized_type = normalize_bc_score_type(score_type) or BC_SCORE_TYPE
    return normalized_type in ALL_BC_SCORE_TYPES


def _counts_extra_points_as_normal(score_type: Optional[str]) -> bool:
    normalized_type = normalize_bc_score_type(score_type) or BC_SCORE_TYPE
    return normalized_type == BC_SCORE_TYPE


def _counts_extra_points_as_abnormal(score_type: Optional[str]) -> bool:
    normalized_type = normalize_bc_score_type(score_type) or BC_SCORE_TYPE
    return normalized_type in {
        BC_SCORE_TYPE_NON_TYPICAL_WHITETAIL,
        BC_SCORE_TYPE_TYPICAL_MULE_DEER,
        BC_SCORE_TYPE_NON_TYPICAL_MULE_DEER,
    }


def _is_non_typical_score_type(score_type: Optional[str]) -> bool:
    normalized_type = normalize_bc_score_type(score_type) or BC_SCORE_TYPE
    return normalized_type in {BC_SCORE_TYPE_NON_TYPICAL_WHITETAIL, BC_SCORE_TYPE_NON_TYPICAL_MULE_DEER}


def _normalize_side(raw_side: Any, score_type: Optional[str]) -> Dict[str, Optional[float]]:
    side_data = raw_side if isinstance(raw_side, dict) else {}
    active_g_labels = set(_active_g_labels(score_type))
    normalized = {"mainBeam": normalize_measurement_input(side_data.get("mainBeam"))}
    for label in G_LABELS:
        normalized[label] = normalize_measurement_input(side_data.get(label)) if label in active_g_labels else None
    for label in H_LABELS:
        normalized[label] = normalize_measurement_input(side_data.get(label))
    normalized["extraPoints"] = normalize_measurement_list(side_data.get("extraPoints")) if _supports_extra_normal_points(score_type) else []
    return normalized


def normalize_measurement_list(value: Any, *, max_items: int = 20) -> List[float]:
    raw_values = value if isinstance(value, list) else []
    normalized: List[float] = []
    for item in raw_values[:max_items]:
        measurement = normalize_measurement_input(item)
        if measurement is not None:
            normalized.append(measurement)
    return normalized


def _get_flat_array_value(raw: Any, key: str, index: int) -> Any:
    values = raw.get(key) if isinstance(raw, dict) else None
    if not isinstance(values, list) or index >= len(values):
        return None
    return values[index]


def _pair_field_labels(entry: Dict[str, Any]) -> Dict[str, str]:
    labels = dict(PAIR_FIELD_LABELS)
    if _counts_extra_points_as_normal(entry.get("type")):
        extra_points_count = max(
            len(entry.get("right", {}).get("extraPoints") or []),
            len(entry.get("left", {}).get("extraPoints") or []),
        )
        for index in range(extra_points_count):
            labels[f"g{8 + index}"] = f"G-{8 + index}"
    return labels


def _pair_fields(entry: Dict[str, Any]) -> Tuple[str, ...]:
    active_fields = ("mainBeam",) + _active_g_labels(entry.get("type")) + H_LABELS
    if not _counts_extra_points_as_normal(entry.get("type")):
        return active_fields
    extra_points_count = max(
        len(entry.get("right", {}).get("extraPoints") or []),
        len(entry.get("left", {}).get("extraPoints") or []),
    )
    extra_fields = tuple(f"g{8 + index}" for index in range(extra_points_count))
    return active_fields + extra_fields


def _side_extra_point_value(side: Dict[str, Any], field_name: str) -> Optional[float]:
    if not field_name.startswith("g"):
        return side.get(field_name)
    if field_name in G_LABELS:
        return side.get(field_name)
    try:
        label_index = int(field_name[1:])
    except ValueError:
        return None
    extra_index = label_index - 8
    extra_points = side.get("extraPoints") or []
    if extra_index < 0 or extra_index >= len(extra_points):
        return None
    return extra_points[extra_index]


def normalize_bc_score_entry(value: Any, disclaimer_accepted: bool) -> Optional[Dict[str, Any]]:
    if not isinstance(value, dict):
        return None

    if "pointsSummary" in value or "spread" in value or "right" in value or "left" in value:
        points_summary = value.get("pointsSummary") if isinstance(value.get("pointsSummary"), dict) else {}
        spread = value.get("spread") if isinstance(value.get("spread"), dict) else {}
        abnormal_points = value.get("abnormalPoints") if isinstance(value.get("abnormalPoints"), dict) else {}
        normalized_type = normalize_bc_score_type(value.get("type")) or BC_SCORE_TYPE
        right = _normalize_side(value.get("right"), normalized_type)
        left = _normalize_side(value.get("left"), normalized_type)
        normalized = {
            "type": normalized_type,
            "enteredManually": True,
            "disclaimerAccepted": bool(disclaimer_accepted),
            "pointsSummary": {
                "rightPointsCount": normalize_points_count(points_summary.get("rightPointsCount")),
                "leftPointsCount": normalize_points_count(points_summary.get("leftPointsCount")),
                "tipToTipSpread": normalize_measurement_input(points_summary.get("tipToTipSpread")),
                "greatestSpread": normalize_measurement_input(points_summary.get("greatestSpread")),
            },
            "spread": {
                "insideSpreadOfMainBeams": normalize_measurement_input(spread.get("insideSpreadOfMainBeams")),
            },
            "abnormalPoints": {
                "right": normalize_measurement_list(abnormal_points.get("right")),
                "left": normalize_measurement_list(abnormal_points.get("left")),
            },
            "right": right,
            "left": left,
        }
    else:
        normalized_type = normalize_bc_score_type(value.get("type")) or BC_SCORE_TYPE
        active_g_labels = set(_active_g_labels(normalized_type))
        right = {
            "mainBeam": normalize_measurement_input(value.get("main_beam_right")),
        }
        left = {
            "mainBeam": normalize_measurement_input(value.get("main_beam_left")),
        }
        for index, label in enumerate(G_LABELS):
            right[label] = (
                normalize_measurement_input(_get_flat_array_value(value, "normal_points_right", index))
                if label in active_g_labels
                else None
            )
            left[label] = (
                normalize_measurement_input(_get_flat_array_value(value, "normal_points_left", index))
                if label in active_g_labels
                else None
            )
        for index, label in enumerate(H_LABELS):
            right[label] = normalize_measurement_input(_get_flat_array_value(value, "circumferences_right", index))
            left[label] = normalize_measurement_input(_get_flat_array_value(value, "circumferences_left", index))
        right["extraPoints"] = normalize_measurement_list(value.get("extra_normal_points_right")) if _supports_extra_normal_points(normalized_type) else []
        left["extraPoints"] = normalize_measurement_list(value.get("extra_normal_points_left")) if _supports_extra_normal_points(normalized_type) else []

        normalized = {
            "type": normalized_type,
            "enteredManually": True,
            "disclaimerAccepted": bool(disclaimer_accepted),
            "pointsSummary": {
                "rightPointsCount": normalize_points_count(value.get("points_right")),
                "leftPointsCount": normalize_points_count(value.get("points_left")),
                "tipToTipSpread": normalize_measurement_input(value.get("spread_tip_to_tip")),
                "greatestSpread": normalize_measurement_input(value.get("spread_greatest")),
            },
            "spread": {
                "insideSpreadOfMainBeams": normalize_measurement_input(value.get("spread_inside_main_beams")),
            },
            "abnormalPoints": {
                "right": normalize_measurement_list(value.get("abnormal_points_right")),
                "left": normalize_measurement_list(value.get("abnormal_points_left")),
            },
            "right": right,
            "left": left,
        }

    if not normalized["abnormalPoints"]["right"]:
        fallback_right_total = normalize_measurement_input(
            abnormal_points.get("rightTotalLength") if "abnormal_points" in locals() else value.get("abnormal_points_right_total")
        )
        if fallback_right_total is not None:
            normalized["abnormalPoints"]["right"] = [fallback_right_total]
    if not normalized["abnormalPoints"]["left"]:
        fallback_left_total = normalize_measurement_input(
            abnormal_points.get("leftTotalLength") if "abnormal_points" in locals() else value.get("abnormal_points_left_total")
        )
        if fallback_left_total is not None:
            normalized["abnormalPoints"]["left"] = [fallback_left_total]

    right_abnormal_total = sum(normalized["abnormalPoints"].get("right") or [])
    left_abnormal_total = sum(normalized["abnormalPoints"].get("left") or [])
    abnormal_total = right_abnormal_total + left_abnormal_total
    normalized["abnormalPoints"]["rightTotalLength"] = round_measurement(right_abnormal_total) if normalized["abnormalPoints"].get("right") else None
    normalized["abnormalPoints"]["leftTotalLength"] = round_measurement(left_abnormal_total) if normalized["abnormalPoints"].get("left") else None
    normalized["abnormalPoints"]["totalLength"] = round_measurement(abnormal_total)

    has_any_value = any(
        value is not None
        for value in [
            normalized["pointsSummary"]["rightPointsCount"],
            normalized["pointsSummary"]["leftPointsCount"],
            normalized["pointsSummary"]["tipToTipSpread"],
            normalized["pointsSummary"]["greatestSpread"],
            normalized["spread"]["insideSpreadOfMainBeams"],
            normalized["abnormalPoints"]["rightTotalLength"],
            normalized["abnormalPoints"]["leftTotalLength"],
            normalized["right"]["mainBeam"],
            normalized["left"]["mainBeam"],
            *[normalized["right"][label] for label in _active_g_labels(normalized["type"])],
            *[normalized["left"][label] for label in _active_g_labels(normalized["type"])],
            *[normalized["right"][label] for label in H_LABELS],
            *[normalized["left"][label] for label in H_LABELS],
            *(normalized["right"].get("extraPoints") or []),
            *(normalized["left"].get("extraPoints") or []),
            *(normalized["abnormalPoints"].get("right") or []),
            *(normalized["abnormalPoints"].get("left") or []),
        ]
    )
    return normalized if has_any_value else None


def calculate_spread_credit(entry: Dict[str, Any]) -> Optional[float]:
    inside_spread = entry.get("spread", {}).get("insideSpreadOfMainBeams")
    right_beam = entry.get("right", {}).get("mainBeam")
    left_beam = entry.get("left", {}).get("mainBeam")
    longer_beam = max(value for value in [right_beam, left_beam] if value is not None) if any(
        value is not None for value in [right_beam, left_beam]
    ) else None
    if inside_spread is None or longer_beam is None:
        return None
    return round_measurement(min(inside_spread, longer_beam))


def _abnormal_points_for_side(entry: Dict[str, Any], side_name: str) -> List[float]:
    abnormal_points = entry.get("abnormalPoints", {}) if isinstance(entry.get("abnormalPoints"), dict) else {}
    side = entry.get(side_name, {}) if isinstance(entry.get(side_name), dict) else {}
    combined_points = list(abnormal_points.get(side_name) or [])
    if _counts_extra_points_as_abnormal(entry.get("type")):
        combined_points.extend(side.get("extraPoints") or [])
    return combined_points


def _sum_side(side: Dict[str, Optional[float]], score_type: Optional[str]) -> float:
    total = side.get("mainBeam") or 0.0
    total += sum(side.get(label) or 0.0 for label in _active_g_labels(score_type))
    total += sum(side.get(label) or 0.0 for label in H_LABELS)
    if _counts_extra_points_as_normal(score_type):
        total += sum(side.get("extraPoints") or [])
    return round(total, 3)


def calculate_typical_whitetail_column_totals(entry: Dict[str, Any]) -> Dict[str, Optional[float]]:
    right = entry.get("right", {}) if isinstance(entry.get("right"), dict) else {}
    left = entry.get("left", {}) if isinstance(entry.get("left"), dict) else {}
    active_g_labels = _active_g_labels(entry.get("type"))
    include_extra_points = _counts_extra_points_as_normal(entry.get("type"))
    has_any_scored_values = any(
        value is not None
        for value in [
            right.get("mainBeam"),
            left.get("mainBeam"),
            *[right.get(label) for label in active_g_labels],
            *[left.get(label) for label in active_g_labels],
            *[right.get(label) for label in H_LABELS],
            *[left.get(label) for label in H_LABELS],
            *(() if not include_extra_points else tuple(right.get("extraPoints") or [])),
            *(() if not include_extra_points else tuple(left.get("extraPoints") or [])),
        ]
    )
    if not has_any_scored_values:
        return {"rightTotal": None, "leftTotal": None}
    return {
        "rightTotal": _sum_side(right, entry.get("type")),
        "leftTotal": _sum_side(left, entry.get("type")),
    }


def calculate_typical_whitetail_deductions(entry: Dict[str, Any]) -> Dict[str, Any]:
    right = entry.get("right", {}) if isinstance(entry.get("right"), dict) else {}
    left = entry.get("left", {}) if isinstance(entry.get("left"), dict) else {}
    differences: Dict[str, Optional[float]] = {}
    paired_total = 0.0
    for field_name in _pair_fields(entry):
        right_value = _side_extra_point_value(right, field_name)
        left_value = _side_extra_point_value(left, field_name)
        if right_value is None and left_value is None:
            differences[field_name] = None
            continue
        difference = abs((right_value or 0.0) - (left_value or 0.0))
        differences[field_name] = round_measurement(difference)
        paired_total += difference

    abnormal_total = sum(_abnormal_points_for_side(entry, "right")) + sum(_abnormal_points_for_side(entry, "left"))
    deductions_total = paired_total if _is_non_typical_score_type(entry.get("type")) else paired_total + abnormal_total

    return {
        "pairedDifferences": differences,
        "pairedDifferencesTotal": round_measurement(paired_total),
        "abnormalDeductionTotal": round_measurement(abnormal_total),
        "deductionsTotal": round_measurement(deductions_total),
    }


def _calculate_subtotal_one(
    spread_credit: Optional[float],
    columns: Dict[str, Optional[float]],
) -> Optional[float]:
    if spread_credit is None and columns["rightTotal"] is None and columns["leftTotal"] is None:
        return None
    return round_measurement((spread_credit or 0.0) + (columns["rightTotal"] or 0.0) + (columns["leftTotal"] or 0.0))


def _calculate_subtotal_two(
    subtotal_one: Optional[float],
    paired_differences_total: Optional[float],
) -> Optional[float]:
    if subtotal_one is None:
        return None
    return round_measurement((subtotal_one or 0.0) - (paired_differences_total or 0.0))


def _calculate_gross_score(
    score_type: Optional[str],
    subtotal_one: Optional[float],
    abnormal_total: Optional[float],
) -> Optional[float]:
    if subtotal_one is None:
        return None
    if _is_non_typical_score_type(score_type):
        return round_measurement((subtotal_one or 0.0) + (abnormal_total or 0.0))
    return round_measurement(subtotal_one)


def calculate_typical_whitetail_final_score(entry: Dict[str, Any]) -> Optional[float]:
    spread_credit = calculate_spread_credit(entry)
    columns = calculate_typical_whitetail_column_totals(entry)
    deductions = calculate_typical_whitetail_deductions(entry)
    subtotal_one = _calculate_subtotal_one(spread_credit, columns)
    subtotal_two = _calculate_subtotal_two(subtotal_one, deductions["pairedDifferencesTotal"])
    if subtotal_one is None or subtotal_two is None:
        return None
    if _is_non_typical_score_type(entry.get("type")):
        return round_measurement(max(0.0, (subtotal_two or 0.0) + (deductions["abnormalDeductionTotal"] or 0.0)))
    return round_measurement(max(0.0, (subtotal_one or 0.0) - (deductions["deductionsTotal"] or 0.0)))


def _highest_filled_label(side: Dict[str, Optional[float]], labels: Tuple[str, ...], trailing_count: int = 0) -> int:
    highest_index = 0
    for index, label in enumerate(labels, start=1):
        if side.get(label) is not None:
            highest_index = index
    if trailing_count > 0:
        highest_index = len(labels) + trailing_count
    return highest_index


def _has_gap_before_later_value(side: Dict[str, Optional[float]], labels: Tuple[str, ...], trailing_count: int = 0) -> bool:
    highest_index = _highest_filled_label(side, labels, trailing_count)
    if highest_index <= 1:
        return False
    for label in labels[: highest_index - 1]:
        if side.get(label) is None:
            return True
    return False


def _required_h_count(side: Dict[str, Optional[float]], score_type: Optional[str]) -> int:
    extra_count = len(side.get("extraPoints") or []) if _counts_extra_points_as_normal(score_type) else 0
    highest_g = _highest_filled_label(side, _active_g_labels(score_type), extra_count)
    return min(4, highest_g)


def validate_bc_score_entry(entry: Dict[str, Any]) -> List[Dict[str, str]]:
    warnings: List[Dict[str, str]] = []
    active_g_labels = _active_g_labels(entry.get("type"))
    include_extra_points = _counts_extra_points_as_normal(entry.get("type"))
    spread_credit = calculate_spread_credit(entry)
    inside_spread = entry.get("spread", {}).get("insideSpreadOfMainBeams")
    right_beam = entry.get("right", {}).get("mainBeam")
    left_beam = entry.get("left", {}).get("mainBeam")
    longer_beam = max(value for value in [right_beam, left_beam] if value is not None) if any(
        value is not None for value in [right_beam, left_beam]
    ) else None
    if (
        inside_spread is not None
        and longer_beam is not None
        and spread_credit is not None
        and inside_spread > longer_beam
    ):
        warnings.append(
            {
                "code": "spread_credit_capped",
                "message": "Inside spread is larger than the longer main beam, so spread credit will be capped.",
            }
        )

    deductions = calculate_typical_whitetail_deductions(entry)
    pair_field_labels = _pair_field_labels(entry)
    for field_name, diff_value in deductions["pairedDifferences"].items():
        if diff_value is not None and diff_value >= ASYMMETRY_WARNING_THRESHOLD:
            warnings.append(
                {
                    "code": "large_left_right_difference",
                    "message": f"{pair_field_labels.get(field_name, field_name)} differs sharply from side to side. Recheck for entry mistakes.",
                }
            )
            break

    for side_name in ("right", "left"):
        side = entry.get(side_name, {}) if isinstance(entry.get(side_name), dict) else {}
        extra_count = len(side.get("extraPoints") or []) if include_extra_points else 0
        if _has_gap_before_later_value(side, active_g_labels, extra_count):
            warnings.append(
                {
                    "code": f"{side_name}_non_contiguous_points",
                    "message": f"{side_name.title()} antler point lengths have a gap before a later point entry.",
                }
            )
        if _has_gap_before_later_value(side, H_LABELS):
            warnings.append(
                {
                    "code": f"{side_name}_non_contiguous_circumferences",
                    "message": f"{side_name.title()} circumference entries have a gap before a later circumference entry.",
                }
            )

        required_h_count = _required_h_count(side, entry.get("type"))
        missing_required_h = [label for label in H_LABELS[:required_h_count] if side.get(label) is None]
        if missing_required_h:
            warnings.append(
                {
                    "code": f"{side_name}_missing_circumferences",
                    "message": f"{side_name.title()} circumference measurements are missing while later point lengths are present.",
                }
            )

    return warnings


def is_bc_score_complete(entry: Dict[str, Any]) -> bool:
    if not entry.get("disclaimerAccepted"):
        return False

    points_summary = entry.get("pointsSummary", {})
    spread = entry.get("spread", {})
    right = entry.get("right", {})
    left = entry.get("left", {})
    abnormal = entry.get("abnormalPoints", {})
    active_g_labels = _active_g_labels(entry.get("type"))
    include_extra_points = _counts_extra_points_as_normal(entry.get("type"))

    required_base_values = [
        points_summary.get("rightPointsCount"),
        points_summary.get("leftPointsCount"),
        points_summary.get("tipToTipSpread"),
        points_summary.get("greatestSpread"),
        spread.get("insideSpreadOfMainBeams"),
        right.get("mainBeam"),
        left.get("mainBeam"),
    ]
    if any(value is None for value in required_base_values):
        return False

    if _has_gap_before_later_value(right, active_g_labels, len(right.get("extraPoints") or []) if include_extra_points else 0) or _has_gap_before_later_value(left, active_g_labels, len(left.get("extraPoints") or []) if include_extra_points else 0):
        return False
    if _has_gap_before_later_value(right, H_LABELS) or _has_gap_before_later_value(left, H_LABELS):
        return False

    for side_name, side in (("right", right), ("left", left)):
        required_h_count = _required_h_count(side, entry.get("type"))
        for label in H_LABELS[:required_h_count]:
            if side.get(label) is None:
                return False

        points_count = points_summary.get(f"{side_name}PointsCount")
        has_any_normal_measurement = any(side.get(label) is not None for label in active_g_labels)
        has_any_normal_measurement = has_any_normal_measurement or (include_extra_points and bool(side.get("extraPoints")))
        has_abnormal_total = bool(_abnormal_points_for_side(entry, side_name)) or abnormal.get(f"{side_name}TotalLength") is not None
        if points_count is not None and points_count > 1 and not has_any_normal_measurement and not has_abnormal_total:
            return False

    return True


def build_bc_score_record(
    entry: Dict[str, Any],
    *,
    calculated_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    effective_calculated_at = calculated_at or datetime.now(timezone.utc)
    if effective_calculated_at.tzinfo is None:
        effective_calculated_at = effective_calculated_at.replace(tzinfo=timezone.utc)
    else:
        effective_calculated_at = effective_calculated_at.astimezone(timezone.utc)
    timestamp = effective_calculated_at.isoformat()
    spread_credit = calculate_spread_credit(entry)
    columns = calculate_typical_whitetail_column_totals(entry)
    deductions = calculate_typical_whitetail_deductions(entry)
    subtotal_one = _calculate_subtotal_one(spread_credit, columns)
    subtotal_two = _calculate_subtotal_two(subtotal_one, deductions["pairedDifferencesTotal"])
    gross_score = _calculate_gross_score(entry.get("type"), subtotal_one, deductions["abnormalDeductionTotal"])
    final_score = calculate_typical_whitetail_final_score(entry)
    status = BC_STATUS_COMPLETE if is_bc_score_complete(entry) else BC_STATUS_DRAFT
    warnings = validate_bc_score_entry(entry)

    right_abnormal_points = _abnormal_points_for_side(entry, "right")
    left_abnormal_points = _abnormal_points_for_side(entry, "left")
    right_abnormal_total = round_measurement(sum(right_abnormal_points)) if right_abnormal_points else None
    left_abnormal_total = round_measurement(sum(left_abnormal_points)) if left_abnormal_points else None
    abnormal_total = round_measurement((sum(right_abnormal_points) + sum(left_abnormal_points)))

    return {
        "type": normalize_bc_score_type(entry.get("type")) or BC_SCORE_TYPE,
        "status": status,
        "enteredManually": True,
        "disclaimerAccepted": bool(entry.get("disclaimerAccepted")),
        "pointsSummary": {
            **entry["pointsSummary"],
        },
        "spread": {
            "insideSpreadOfMainBeams": entry["spread"].get("insideSpreadOfMainBeams"),
            "spreadCredit": spread_credit,
        },
        "abnormalPoints": {
            "right": entry["abnormalPoints"].get("right") or [],
            "left": entry["abnormalPoints"].get("left") or [],
            "rightTotalLength": right_abnormal_total,
            "leftTotalLength": left_abnormal_total,
            "totalLength": abnormal_total,
        },
        "right": entry["right"],
        "left": entry["left"],
        "computed": {
            "rightTotal": columns["rightTotal"],
            "leftTotal": columns["leftTotal"],
            "subtotalOne": subtotal_one,
            "pairedDifferencesTotal": deductions["pairedDifferencesTotal"],
            "abnormalDeductionTotal": deductions["abnormalDeductionTotal"],
            "deductionsTotal": deductions["deductionsTotal"],
            "subtotalTwo": subtotal_two,
            "grossScore": gross_score,
            "finalScore": final_score,
        },
        "differences": deductions["pairedDifferences"],
        "warnings": warnings,
        "calculatedAt": timestamp,
        "updatedAt": timestamp,
    }


def normalize_saved_bc_score(score: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(score, dict):
        return None
    normalized_type = normalize_bc_score_type(score.get("type"))
    right = score.get("right") if isinstance(score.get("right"), dict) else {}
    left = score.get("left") if isinstance(score.get("left"), dict) else {}
    requires_non_typical_whitetail_rebuild = normalized_type == BC_SCORE_TYPE_NON_TYPICAL_WHITETAIL and (
        bool(right.get("extraPoints")) or bool(left.get("extraPoints"))
    )
    if (
        normalized_type in ALL_BC_SCORE_TYPES
        and isinstance(score.get("computed"), dict)
        and "subtotalOne" in score.get("computed", {})
        and "subtotalTwo" in score.get("computed", {})
        and not requires_non_typical_whitetail_rebuild
    ):
        return score

    measurements = score.get("measurements") if isinstance(score.get("measurements"), dict) else score
    normalized_entry = normalize_bc_score_entry(measurements, bool(score.get("disclaimerAccepted", True)))
    if normalized_entry is None:
        return None
    return build_bc_score_record(normalized_entry)
