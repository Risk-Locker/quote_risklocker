"""Deterministic Pure-Decimal Closed-Loop Accounting Proof Gate.

Verifies Malaysian Motor Quotation arithmetic invariants using strict Decimal precision:
1. Sum of itemized optional riders == stated total_optional_cover_amount (when present).
2. Basic Premium - NCD + Loading + Optional Riders == Gross Premium (when breakdown is present).
3. Gross Premium + SST + Stamp Duty - Insurer Rebate == Underwriter Final Total Payable.
4. Rejects conditional excess footnotes (e.g. RM 400.00 under Clause 2(f)) and Sum Insured leaks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
from typing import Any

_ZERO = Decimal("0.00")
_CENT = Decimal("0.01")
_OPTIONAL_TOL = Decimal("0.15")
_GROSS_TOL = Decimal("0.25")
_PAYABLE_TOL = Decimal("0.15")


def _to_decimal(raw: Any) -> Decimal | None:
    if raw is None:
        return None
    if isinstance(raw, Decimal):
        return raw.quantize(_CENT, rounding=ROUND_HALF_UP)
    if isinstance(raw, int):
        return Decimal(raw).quantize(_CENT, rounding=ROUND_HALF_UP)
    txt = str(raw).strip()
    if not txt:
        return None
    cleaned = re.sub(r"[^\d.\-]", "", txt.replace(",", ""))
    if not cleaned or cleaned in {"-", ".", "-."}:
        return None
    try:
        return Decimal(cleaned).quantize(_CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return None


def _abs_decimal(raw: Any) -> Decimal:
    dec = _to_decimal(raw)
    if dec is None:
        return _ZERO
    return abs(dec)


@dataclass(frozen=True)
class AccountingProofVerdict:
    passed: bool
    authoritative_motor_premium: Decimal | None
    sum_optional_riders: Decimal = _ZERO
    expected_gross: Decimal | None = None
    expected_payable: Decimal | None = None
    discrepancies: list[str] = field(default_factory=list)
    quarantine_reason: str | None = None


def compute_optional_riders_sum(gemini_res: dict[str, Any]) -> Decimal:
    """Sum positive RM costs across detected_benefits and non-duplicated detected_packs."""
    benefits = gemini_res.get("detected_benefits") or []
    packs = gemini_res.get("detected_packs") or []

    benefit_sum = _ZERO
    seen_benefit_labels: list[str] = []
    for item in benefits:
        if not isinstance(item, dict):
            continue
        cost_dec = _to_decimal(item.get("premium_cost"))
        if cost_dec is not None and cost_dec > _ZERO:
            benefit_sum += cost_dec
            seen_benefit_labels.append(str(item.get("label") or "").strip().lower())

    pack_extra_sum = _ZERO
    for pack in packs:
        if not isinstance(pack, dict):
            continue
        p_cost = _to_decimal(pack.get("price"))
        if p_cost is None or p_cost <= _ZERO:
            continue
        p_name = str(pack.get("package_name") or "").strip().lower()
        already_counted = any(p_name and (p_name in lbl or lbl in p_name) for lbl in seen_benefit_labels if lbl)
        if not already_counted:
            pack_extra_sum += p_cost

    return (benefit_sum + pack_extra_sum).quantize(_CENT, rounding=ROUND_HALF_UP)


def verify_quotation_accounting(
    gemini_res: dict[str, Any],
    *,
    is_covernote: bool = False,
) -> AccountingProofVerdict:
    """Validate bottom-up & top-down accounting equations and select authoritative insurer payable."""
    discrepancies: list[str] = []

    basic_dec = _abs_decimal(gemini_res.get("basic_premium"))
    ncd_dec = _abs_decimal(gemini_res.get("ncd_amount"))
    loading_dec = _abs_decimal(gemini_res.get("loading_amount"))
    gross_dec = _abs_decimal(gemini_res.get("gross_premium"))
    sst_dec = _abs_decimal(gemini_res.get("service_tax"))
    stamp_dec = _abs_decimal(gemini_res.get("stamp_duty"))
    rebate_dec = _abs_decimal(gemini_res.get("insurer_rebate"))
    stated_opt_dec = _abs_decimal(gemini_res.get("total_optional_cover_amount"))
    raw_prem_dec = _to_decimal(gemini_res.get("premium"))
    raw_total_dec = _to_decimal(gemini_res.get("total_amount"))
    sum_insured_dec = _abs_decimal(gemini_res.get("coverage_amount") or gemini_res.get("sum_insured"))
    cov_type = str(gemini_res.get("coverage_type") or "").lower()

    riders_sum = compute_optional_riders_sum(gemini_res)

    # Identity 1: Itemized optional riders sum == stated total_optional_cover_amount
    if stated_opt_dec > _ZERO and riders_sum > _ZERO:
        diff_opt = abs(riders_sum - stated_opt_dec)
        if diff_opt > _OPTIONAL_TOL:
            discrepancies.append(
                f"Optional covers sum RM {riders_sum:.2f} != stated optional cover total RM {stated_opt_dec:.2f} (delta RM {diff_opt:.2f})."
            )
    elif stated_opt_dec > _ZERO and riders_sum == _ZERO:
        discrepancies.append(
            f"Stated total_optional_cover_amount RM {stated_opt_dec:.2f} present, but detected_benefits returned RM 0.00 in itemized rider prices."
        )

    eff_riders = riders_sum if riders_sum > _ZERO else stated_opt_dec

    # Identity 2: Basic - NCD + Loading + Optional Riders == Gross Premium
    expected_gross: Decimal | None = None
    if basic_dec > _ZERO:
        expected_gross = (basic_dec - ncd_dec + loading_dec + eff_riders).quantize(_CENT, rounding=ROUND_HALF_UP)
        if gross_dec > _ZERO:
            gross_delta = gross_dec - expected_gross
            if abs(gross_delta) > _GROSS_TOL:
                if abs(gross_delta) == _abs_decimal(loading_dec) or (loading_dec == _ZERO and gross_delta > _ZERO):
                    discrepancies.append(
                        f"Gross equation gap RM {gross_delta:.2f}: Basic ({basic_dec:.2f}) - NCD ({ncd_dec:.2f}) + Loading ({loading_dec:.2f}) + Riders ({eff_riders:.2f}) = {expected_gross:.2f} vs Gross ({gross_dec:.2f}) — check missed loading or rider."
                    )
                else:
                    discrepancies.append(
                        f"Gross mismatch: expected RM {expected_gross:.2f} vs extracted Gross RM {gross_dec:.2f} (delta RM {abs(gross_delta):.2f})."
                    )

    # Identity 3: Gross + SST + Stamp - Insurer Rebate == Final Insurer Payable
    expected_payable: Decimal | None = None
    effective_gross_for_payable = gross_dec if gross_dec > _ZERO else expected_gross
    if effective_gross_for_payable is not None and effective_gross_for_payable > _ZERO:
        expected_payable = (effective_gross_for_payable + sst_dec + stamp_dec - rebate_dec).quantize(_CENT, rounding=ROUND_HALF_UP)

    authoritative: Decimal | None = None
    if raw_total_dec is not None and raw_total_dec > _ZERO:
        authoritative = raw_total_dec
    elif raw_prem_dec is not None and raw_prem_dec > _ZERO:
        authoritative = raw_prem_dec

    if expected_payable is not None and expected_payable > _ZERO:
        matches_total = raw_total_dec is not None and abs(expected_payable - raw_total_dec) <= _PAYABLE_TOL
        matches_prem = raw_prem_dec is not None and abs(expected_payable - raw_prem_dec) <= _PAYABLE_TOL
        if matches_prem and not matches_total:
            # e.g., total_amount accidentally picked up non-insurance road tax or a post-total note, while premium matched Gross+SST+Stamp
            authoritative = raw_prem_dec
        elif matches_total:
            authoritative = raw_total_dec
        elif raw_total_dec is not None and raw_total_dec > _ZERO:
            delta_pay = abs(expected_payable - raw_total_dec)
            discrepancies.append(
                f"Final Payable mismatch: Gross ({effective_gross_for_payable:.2f}) + SST ({sst_dec:.2f}) + Stamp ({stamp_dec:.2f}) - Rebate ({rebate_dec:.2f}) = RM {expected_payable:.2f} vs extracted Total RM {raw_total_dec:.2f} (delta RM {delta_pay:.2f})."
            )
            # When Gross+SST+Stamp breakdown is internally consistent (Identity 2 passed or no gross conflict), prefer calculated payable over stray RM 400 footnote
            if raw_total_dec == Decimal("400.00") and expected_payable > Decimal("400.00"):
                authoritative = expected_payable
        else:
            authoritative = expected_payable

    # Conditional Compulsory Excess Footnote Trap (RM 400.00 clause 2(f)) & Sum Insured sanity
    if not is_covernote and "comprehensive" in cov_type:
        if sum_insured_dec < Decimal("1000.00"):
            discrepancies.append(f"Sum insured suspiciously low/missing for Comprehensive: RM {sum_insured_dec:.2f}.")
        if authoritative is not None and authoritative == Decimal("400.00") and sum_insured_dec >= Decimal("10000.00"):
            discrepancies.append(
                "Extracted total RM 400.00 matches Malaysian Compulsory Excess footnote trap rather than motor premium."
            )
        if authoritative is not None and sum_insured_dec >= Decimal("10000.00") and authoritative == sum_insured_dec:
            discrepancies.append(
                f"Extracted total RM {authoritative:.2f} equals Sum Insured RM {sum_insured_dec:.2f}; likely column mix-up."
            )

    quarantine_reason: str | None = None
    if discrepancies:
        quarantine_reason = "; ".join(discrepancies[:3])

    return AccountingProofVerdict(
        passed=(len(discrepancies) == 0),
        authoritative_motor_premium=authoritative,
        sum_optional_riders=riders_sum,
        expected_gross=expected_gross,
        expected_payable=expected_payable,
        discrepancies=discrepancies,
        quarantine_reason=quarantine_reason,
    )
