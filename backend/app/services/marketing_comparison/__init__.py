"""Marketing Comparison Package Facade.

Maintains 100% backward compatibility for all modules importing from
app.services.marketing_comparison_service or app.services.marketing_comparison.
"""

from app.services.marketing_comparison.ncd_evaluator import (
    COMMERCIAL_NCD_SCALE,
    NCD_RATE_SCALE,
    calculate_betterment_rate,
    calculate_ncd_pair,
    calculate_vehicle_age,
    check_has_betterment_peril,
    evaluate_betterment_rules,
    get_standard_betterment_rate,
    normalize_towing_km,
    rank_comparison_entries,
)
from app.services.marketing_comparison.whatsapp_formatter import (
    format_whatsapp_teaser,
    format_whatsapp_teaser_from_data,
)
from app.services.marketing_comparison.covernote_classifier import (
    is_covernote_document,
)
from app.services.marketing_comparison.towing_evaluator import (
    resolve_insurer_towing_limit,
)
from app.services.marketing_comparison.benefits_extractor import (
    _extract_exact_basic_figure,
    _extract_excess,
    _extract_ncd_from_draft,
    _extract_source_quotation_no,
    _extract_val,
    _extract_valuation_type,
    _extract_vehicle_basic_premium,
    _extract_vehicle_motor_premium,
    _extract_vehicle_sum_insured,
    _extract_vehicle_year_from_draft,
    _extract_windscreen_from_draft,
    _is_valid_extracted_qno,
    _is_valid_windscreen_amt,
    _resolve_comparison_benefits,
    _safe_str,
    _to_float,
    calculate_exact_rate,
    detect_runner_fee_from_id,
    extract_strict_schedule_excess,
    format_canonical_perils,
)

__all__ = [
    "COMMERCIAL_NCD_SCALE",
    "NCD_RATE_SCALE",
    "calculate_betterment_rate",
    "calculate_ncd_pair",
    "calculate_vehicle_age",
    "check_has_betterment_peril",
    "evaluate_betterment_rules",
    "get_standard_betterment_rate",
    "normalize_towing_km",
    "rank_comparison_entries",
    "format_whatsapp_teaser",
    "format_whatsapp_teaser_from_data",
    "is_covernote_document",
    "resolve_insurer_towing_limit",
    "_extract_exact_basic_figure",
    "_extract_excess",
    "_extract_ncd_from_draft",
    "_extract_source_quotation_no",
    "_extract_val",
    "_extract_valuation_type",
    "_extract_vehicle_basic_premium",
    "_extract_vehicle_motor_premium",
    "_extract_vehicle_sum_insured",
    "_extract_vehicle_year_from_draft",
    "_extract_windscreen_from_draft",
    "_is_valid_extracted_qno",
    "_is_valid_windscreen_amt",
    "_resolve_comparison_benefits",
    "_safe_str",
    "_to_float",
    "calculate_exact_rate",
    "detect_runner_fee_from_id",
    "extract_strict_schedule_excess",
    "format_canonical_perils",
]
