"""Deterministic Bundled Benefit & Plan Tier Matching Engine.

Provides one shared matcher used across extraction mapping, quotation workspace / Design 2
(`render_context.py`), and the Comparison Matrix (`benefits_extractor.py`).
"""

from __future__ import annotations

import re
from typing import Any

_RANGE_RE = re.compile(r"\b(?:\d+\s*[-–/]\s*\d+|[a-d]\s*[-–/]\s*[a-d])\b", re.IGNORECASE)
_BASE_AUTO365_POLICY_RE = re.compile(
    r"\bauto\s*365\b(?:\s+comprehensive)?\s*(?:lite|plus|premier|all[- ]?inclusive)?\b",
    re.IGNORECASE,
)


def _norm_text(raw: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (raw or "").lower()).strip()


def _strip_ranges(raw: str | None) -> str:
    return _RANGE_RE.sub(" ", raw or "")


def is_base_auto365_policy_label(raw: str | None) -> bool:
    """True when text names AmAssurance's base policy tier rather than Private Car 365 add-on."""
    s = (raw or "").lower()
    if "private car 365" in s or "pc365" in s or "pc 365" in s or "365 plan" in s:
        return False
    return bool(_BASE_AUTO365_POLICY_RE.search(s))


def extract_plan_tier_token(raw: str | None) -> str | None:
    """Extract normalized plan tier ('Plan 1', 'Plan 2', 'EV Plan', 'Plan A', etc.) safely."""
    cleaned = _strip_ranges(raw)
    if not cleaned.strip():
        return None
    low = cleaned.lower()

    if re.search(r"\bev\s*plan\b|\bsmart\s*driver\s*ev\b|\bplan\s*ev\b", low):
        return "EV Plan"

    m = re.search(r"\b(?:plan|pelan|tier|pakej)\s*(?:no\.?\s*)?([1-9]|[a-d])\b", low)
    if m:
        tok = m.group(1).upper()
        return f"Plan {tok}"

    m_named = re.search(
        r"\b(?:motor\s*pa(?:\s*plus|\+)?|private\s*car\s*365|pc\s*365|365|smart\s*driver|e-?assist(?:\s*smart\s*driver)?|sdpa|driver\s*(?:&|and)?\s*passenger\s*(?:protection|protector|pa)|dpp)\s*[-:]?\s*(?:plan|pelan)?\s*([1-9]|[a-d])\b",
        low,
    )
    if m_named:
        tok = m_named.group(1).upper()
        return f"Plan {tok}"

    m_short = re.search(r"\bp([1-4])\b", low)
    if m_short:
        return f"Plan {m_short.group(1)}"

    return None


def bundle_matches_catalog(bundle: Any, catalog_name: str | None = None) -> bool:
    scope = (getattr(bundle, "catalog_scope", None) or "").strip().lower()
    if not scope:
        return True
    if not catalog_name:
        return True
    return scope in catalog_name.lower()


def _selection_text_haystack(selection: Any, offering: Any = None, concept: Any = None) -> str:
    ev_snap = getattr(selection, "evidence_snapshot", None)
    if not isinstance(ev_snap, dict):
        ev_snap = {}
    tv = getattr(selection, "typed_value_override", None) or getattr(offering, "typed_value", None)
    tv_text = ""
    if isinstance(tv, dict):
        tv_text = " ".join(
            str(tv.get(k) or "")
            for k in ("plan_key", "enum_key", "display_text", "value")
        )
    parts = [
        str(ev_snap.get("plan_tier") or ""),
        str(ev_snap.get("extracted_label") or ""),
        str(ev_snap.get("raw_text") or ""),
        str(ev_snap.get("coverage_limit") or ""),
        str(getattr(selection, "label_override", None) or ""),
        str(getattr(selection, "selection_key", None) or ""),
        str(getattr(offering, "label_override", None) or ""),
        str(getattr(offering, "offering_key", None) or ""),
        str(getattr(concept, "label", None) or ""),
        tv_text,
    ]
    return " ".join(p for p in parts if p)


def match_bundle_for_selection(
    selection: Any,
    offering: Any,
    concept: Any,
    bundles: list[Any] | None,
    catalog_name: str | None = None,
) -> Any | None:
    if not bundles:
        return None
    cid = str(getattr(selection, "concept_id", None) or getattr(offering, "concept_id", None) or getattr(concept, "id", None) or "")
    raw_haystack = _selection_text_haystack(selection, offering, concept)
    if is_base_auto365_policy_label(raw_haystack) and not any(
        k in raw_haystack.lower() for k in ("private car 365", "pc365", "pc 365", "365 plan")
    ):
        # Never mistake base policy 'auto365 Lite/Plus/Premier' for Private Car 365 add-on
        return None

    padded = f" {_norm_text(raw_haystack)} "
    for bundle in sorted(bundles, key=lambda b: (int(getattr(b, "sort_order", 0) or 0), str(getattr(b, "name", "")))):
        if not getattr(bundle, "is_active", True):
            continue
        if not bundle_matches_catalog(bundle, catalog_name):
            continue
        trig_ids = {str(getattr(bundle, "primary_concept_id", "") or "")}
        trig_ids.update(str(x) for x in (getattr(bundle, "trigger_concept_ids", None) or []) if x)
        if cid and cid in trig_ids:
            return bundle
        for alias in (getattr(bundle, "match_aliases", None) or []):
            norm_a = _norm_text(str(alias))
            if norm_a and f" {norm_a} " in padded:
                return bundle
    return None


def match_bundle_for_text(
    text: str,
    bundles: list[Any] | None,
    catalog_name: str | None = None,
    concept_id: str | None = None,
) -> Any | None:
    if not bundles:
        return None
    if is_base_auto365_policy_label(text) and not any(
        k in (text or "").lower() for k in ("private car 365", "pc365", "pc 365", "365 plan")
    ):
        return None
    padded = f" {_norm_text(text)} "
    cid = str(concept_id or "")
    for bundle in sorted(bundles, key=lambda b: (int(getattr(b, "sort_order", 0) or 0), str(getattr(b, "name", "")))):
        if not getattr(bundle, "is_active", True):
            continue
        if not bundle_matches_catalog(bundle, catalog_name):
            continue
        trig_ids = {str(getattr(bundle, "primary_concept_id", "") or "")}
        trig_ids.update(str(x) for x in (getattr(bundle, "trigger_concept_ids", None) or []) if x)
        if cid and cid in trig_ids:
            return bundle
        for alias in (getattr(bundle, "match_aliases", None) or []):
            norm_a = _norm_text(str(alias))
            if norm_a and f" {norm_a} " in padded:
                return bundle
    return None


def match_tier_from_text(bundle: Any, raw_text: str) -> tuple[Any | None, bool]:
    """Match a bundle tier from text. Returns (tier, is_uncertain_default)."""
    tiers = sorted(
        list(getattr(bundle, "tiers", None) or []),
        key=lambda t: (int(getattr(t, "sort_order", 0) or 0), str(getattr(t, "tier_key", "") or "")),
    )
    if not tiers:
        return None, False

    fallback = next((t for t in tiers if getattr(t, "is_default_fallback", False)), tiers[0])
    if not getattr(bundle, "has_plan_tiers", False):
        return fallback, False

    range_free = _strip_ranges(raw_text)
    padded_norm = f" {_norm_text(range_free)} "
    extracted_tok = extract_plan_tier_token(range_free)
    extracted_norm = _norm_text(extracted_tok) if extracted_tok else ""

    for tier in tiers:
        candidates = [
            str(getattr(tier, "label", "") or ""),
            str(getattr(tier, "tier_key", "") or "").replace("_", " "),
            *(str(tok) for tok in (getattr(tier, "match_tokens", None) or [])),
        ]
        for cand in candidates:
            norm_c = _norm_text(cand)
            if not norm_c:
                continue
            if extracted_norm and norm_c == extracted_norm:
                return tier, False
            if re.search(rf"\b{re.escape(norm_c)}\b", padded_norm):
                return tier, False

    # Pass 3: match against tier effect towing limits (non-fallback tiers first, highest sort_order first)
    neg_unlim_re = re.compile(r"\b(?:not|no|non|without)\s+unlimited\b", re.IGNORECASE)
    pass3_tiers = sorted(
        tiers,
        key=lambda t: (1 if getattr(t, "is_default_fallback", False) else 0, -int(getattr(t, "sort_order", 0) or 0)),
    )
    for tier in pass3_tiers:
        for eff in sorted(list(getattr(tier, "effects", None) or []), key=lambda x: int(getattr(x, "sort_order", 0) or 0)):
            eff_type = str(getattr(eff, "effect_type", "") or "")
            if eff_type not in ("upgrade_to_box2", "add_to_box2"):
                continue
            title = str(getattr(eff, "display_title", "") or "")
            cv = str(getattr(eff, "comparison_value", "") or "")
            if "towing" not in title.lower() and not cv:
                continue
            eff_blob = f"{cv} {title}".lower()
            if "unlimited" in eff_blob:
                if (
                    re.search(r"\bunlimited(?:\s+(?:towing|mileage|distance|km|auto\s+assistance))?\b", padded_norm)
                    and not neg_unlim_re.search(range_free)
                ):
                    return tier, False
                continue
            m_km = re.search(r"\b(\d+)\s*km\b", eff_blob)
            if m_km:
                num = re.escape(m_km.group(1))
                if re.search(rf"\b{num}\s*km\b", padded_norm):
                    return tier, False
                continue
            m_rm = re.search(r"\b(?:rm|myr)\s*([\d,]+)\b", eff_blob)
            if m_rm:
                num = re.escape(m_rm.group(1).replace(",", ""))
                if re.search(rf"\b(?:rm|myr)\s*{num}\b", padded_norm):
                    return tier, False

    return fallback, True


def resolve_bundle_tier(
    bundle: Any,
    selection: Any = None,
    offering: Any = None,
    extra_text: str = "",
) -> tuple[Any | None, bool]:
    """Resolve persisted or inferred tier for a bundle selection.

    Returns (tier, is_uncertain_default).
    """
    tiers = sorted(
        list(getattr(bundle, "tiers", None) or []),
        key=lambda t: (int(getattr(t, "sort_order", 0) or 0), str(getattr(t, "tier_key", "") or "")),
    )
    if not tiers:
        return None, False

    ev_snap = getattr(selection, "evidence_snapshot", None) if selection is not None else None
    if not isinstance(ev_snap, dict):
        ev_snap = {}

    saved_tid = str(getattr(selection, "bundle_tier_id", None) or "") if selection is not None else ""
    if saved_tid:
        matched_saved = next((t for t in tiers if str(t.id) == saved_tid), None)
        if matched_saved is not None:
            return matched_saved, bool(ev_snap.get("plan_tier_uncertain", False))

    if not getattr(bundle, "has_plan_tiers", False):
        fallback = next((t for t in tiers if getattr(t, "is_default_fallback", False)), tiers[0])
        return fallback, False

    haystack = " ".join(
        p
        for p in [
            _selection_text_haystack(selection, offering, None) if selection is not None else "",
            extra_text,
        ]
        if p
    )
    return match_tier_from_text(bundle, haystack)
