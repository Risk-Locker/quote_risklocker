"""Marketing Comparison API router."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user, settings_dep
from app.core.config import Settings
from app.db.session import get_db
from app.models.tables import InsuranceTenure, Session as SessionModel, TenureComparisonEntry, User, new_id
from app.services.marketing_comparison_service import (
    delete_comparison_entry,
    format_whatsapp_teaser,
    generate_all_quotations,
    generate_quotation_for_entry,
    get_marketing_comparison,
    rank_comparison_entries,
    refresh_tenure_ledger,
    rescan_comparison_tenure,
    reset_comparison_entry_to_detected,
    save_comparison_entry,
    select_winner_and_generate_draft,
    update_tenure_fixed_costs,
)
from app.services.insurance_tenure_service import record_stage_timestamp
from app.services.upload_intake_service import create_queued_upload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/comparison", tags=["marketing-comparison"])


import re
from pydantic import field_validator

def _parse_flexible_float(v: any) -> float | None:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).lower()
    if any(k in s for k in ("included", "free", "yes", "na", "n/a", "nil", "none")):
        return 0.0
    s = re.sub(r'[^\d\.\-]', '', str(v))
    try:
        return float(s) if s else 0.0
    except Exception:
        return 0.0

def _parse_flexible_bool(v: any) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    s = str(v).lower()
    return "yes" in s or "true" in s or "included" in s or "1" in s or "on" in s

class FixedCostsUpdateRequest(BaseModel):
    road_tax: float = Field(0.0, description="Road tax amount in MYR")
    runner_fee: float = Field(0.0, description="Runner / agent service fee in MYR")
    windscreen_target: float | None = Field(None, description="Windscreen coverage amount in MYR")
    ncd_percentage: float | None = Field(None, description="NCD percentage (e.g. 55.0)")
    coverage_start_date: str | None = Field(None, description="ISO format or YYYY-MM-DD for insurance start date")
    coverage_end_date: str | None = Field(None, description="ISO format or YYYY-MM-DD for insurance end date")
    customer_name: str | None = Field(None, description="Customer name")
    ic_no: str | None = Field(None, description="Malaysian IC or Passport number")
    engine_cc: str | None = Field(None, description="Engine CC (e.g. 1496 CC)")
    engine_no: str | None = Field(None, description="Engine number")
    chassis_no: str | None = Field(None, description="Chassis / VIN number")
    vehicle_model: str | None = Field(None, description="Vehicle make and model")
    manufacture_year: int | None = Field(None, description="Vehicle year of manufacture (e.g. 2020)")

    @field_validator("road_tax", "runner_fee", "windscreen_target", "ncd_percentage", mode="before")
    def parse_floats(cls, v):
        return _parse_flexible_float(v)


class ComparisonEntryUpsertRequest(BaseModel):
    id: str | None = None
    company_name: str
    sum_insured: float = 0.0
    valuation_type: str = "market_value"
    motor_premium: float = 0.0
    towing_limit: str = "Unlimited"
    agreed_value: bool = False
    waiver_betterment: bool = False
    excess: float = 0.0
    windscreen_sum_insured: float | None = None
    special_perils: str | None = None
    llp_llop: str | None = None
    is_recommended: bool = False
    is_manual: bool = True
    notes: str | None = None
    basic_figure_amount: float | None = None
    source_quotation_no: str | None = None

    @field_validator("sum_insured", "motor_premium", "excess", "windscreen_sum_insured", "basic_figure_amount", mode="before")
    def parse_floats(cls, v):
        return _parse_flexible_float(v)

    @field_validator("agreed_value", "waiver_betterment", "is_recommended", "is_manual", mode="before")
    def parse_bools(cls, v):
        return _parse_flexible_bool(v)


class SelectWinnerRequest(BaseModel):
    entry_id: str = Field(..., description="ID of the winning comparison entry")
    force_state: bool | None = Field(None, description="Optional explicit boolean state; if None, toggles current state")


@router.get("/{tenure_id}")
def get_comparison(
    tenure_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Retrieve full marketing comparison matrix for an insurance tenure."""
    try:
        return get_marketing_comparison(db, tenure_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.exception("Failed to retrieve marketing comparison for tenure %s: %s", tenure_id, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load comparison")


@router.post("/{tenure_id}/refresh-ledger")
def refresh_ledger(
    tenure_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Re-extract customer & vehicle ledger from uploaded quotations via recency waterfall, recalculating road tax dynamically."""
    try:
        return refresh_tenure_ledger(db, tenure_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.exception("Failed to refresh ledger for tenure %s: %s", tenure_id, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to refresh ledger")


@router.post("/{tenure_id}/fixed-costs")
def update_fixed_costs(
    tenure_id: str,
    payload: FixedCostsUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Update tenure-level fixed costs and coverage dates."""
    try:
        return update_tenure_fixed_costs(
            db,
            tenure_id,
            road_tax=payload.road_tax,
            runner_fee=payload.runner_fee,
            windscreen_target=payload.windscreen_target,
            ncd_percentage=payload.ncd_percentage,
            coverage_start_date=payload.coverage_start_date,
            coverage_end_date=payload.coverage_end_date,
            customer_name=payload.customer_name,
            ic_no=payload.ic_no,
            engine_cc=payload.engine_cc,
            engine_no=payload.engine_no,
            chassis_no=payload.chassis_no,
            vehicle_model=payload.vehicle_model,
            manufacture_year=payload.manufacture_year,
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.exception("Failed to update fixed costs for tenure %s: %s", tenure_id, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update fixed costs")


@router.post("/{tenure_id}/entry")
def upsert_entry(
    tenure_id: str,
    payload: ComparisonEntryUpsertRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Create or update an underwriter comparison column."""
    try:
        return save_comparison_entry(db, tenure_id, payload.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.exception("Failed to upsert comparison entry for tenure %s: %s", tenure_id, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save entry")


@router.delete("/{tenure_id}/entry/{entry_id}")
def delete_entry(
    tenure_id: str,
    entry_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Delete a comparison column."""
    try:
        return delete_comparison_entry(db, tenure_id, entry_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.exception("Failed to delete entry %s in tenure %s: %s", entry_id, tenure_id, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete entry")


@router.post("/{tenure_id}/entry/{entry_id}/reset")
def reset_entry(
    tenure_id: str,
    entry_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Reset a manual override back to original AI detected values for a specific entry."""
    try:
        return reset_comparison_entry_to_detected(db, tenure_id, entry_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.exception("Failed to reset entry %s in tenure %s: %s", entry_id, tenure_id, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to reset entry")


@router.post("/{tenure_id}/winner")
def choose_winner(
    tenure_id: str,
    payload: SelectWinnerRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Select or toggle the winning underwriter from comparison and prepare Quotation Builder draft."""
    try:
        return select_winner_and_generate_draft(
            db,
            tenure_id,
            payload.entry_id,
            user.id,
            force_state=payload.force_state,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.exception("Failed to select winner for tenure %s: %s", tenure_id, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to select winner")


@router.get("/{tenure_id}/whatsapp-teaser")
def get_whatsapp_teaser(
    tenure_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Generate executive Malaysian WhatsApp teaser text for client messaging."""
    try:
        teaser_text = format_whatsapp_teaser(db, tenure_id)
        tenure = db.get(InsuranceTenure, tenure_id)
        if tenure:
            if tenure.stage in ("Quotations", "Prospecting", "draft", None):
                tenure.stage = "Material to Client"
            record_stage_timestamp(tenure, "Material to Client")
            db.commit()
        return {"status": "success", "teaser_text": teaser_text}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.exception("Failed to generate WhatsApp teaser for tenure %s: %s", tenure_id, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to format teaser")


@router.post("/{tenure_id}/upload-quote")
async def upload_comparison_quote(
    tenure_id: str,
    file: UploadFile = File(...),
    is_test: bool = Form(False),
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Upload an underwriter quotation PDF directly into this comparison deal.

    Enqueues the document, extracts quotation figures, and binds the session directly
    to the active insurance tenure so it immediately appears as a comparison column.
    """
    tenure = db.get(InsuranceTenure, tenure_id)
    if not tenure:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Tenure {tenure_id} not found")

    # Check if filename specifies a date and verify against tenure coverage period
    fname = file.filename or ""
    date_match = re.search(r"(?:^|[_\-\s])(\d{4})(\d{2})(\d{2})(?:[_\-\s]|\.pdf)", fname, re.IGNORECASE)
    if date_match and tenure.coverage_start_date:
        y, m, d = date_match.groups()
        file_date_str = f"{y}{m}{d}"
        tenure_date_str = tenure.coverage_start_date.strftime("%Y%m%d")
        if file_date_str != tenure_date_str:
            target_fmt = tenure.coverage_start_date.strftime("%d/%m/%Y")
            file_fmt = f"{d}/{m}/{y}"
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot upload: quotation validity date ({file_fmt}) does not match this comparison period ({target_fmt}).",
            )

    idempotency_key = f"comp_{tenure_id}_{new_id()[:12]}"
    try:
        queued = await create_queued_upload(
            db,
            settings,
            owner_id=user.id,
            upload=file,
            idempotency_key=idempotency_key,
            enhanced_reading=False,
            is_test=is_test,
            tenure_id=tenure_id,
        )
        if queued.session:
            queued.session.tenure_id = tenure_id
            queued.session.is_tenure_active = True
            if tenure.stage in ("Prospecting", "draft", None):
                tenure.stage = "Quotations"
            record_stage_timestamp(tenure, "Quotations")
            db.commit()

        return {
            "status": "success",
            "session_id": queued.session.id if queued.session else None,
            "job_id": queued.job.id if queued.job else None,
            "uploaded_file_id": queued.uploaded_file.id if queued.uploaded_file else None,
        }
    except Exception as e:
        logger.exception("Failed to upload quotation PDF for tenure %s: %s", tenure_id, e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{tenure_id}/entry/{entry_id}/generate-quote")
def generate_single_entry_quote(
    tenure_id: str,
    entry_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Generate official Risk-Locker quotation for a specific comparison card."""
    try:
        return generate_quotation_for_entry(db, tenure_id, entry_id, user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.exception("Failed to generate quote for entry %s under tenure %s: %s", entry_id, tenure_id, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate quote")


@router.post("/{tenure_id}/generate-all-quotes")
def generate_all_deal_quotes(
    tenure_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Generate official Risk-Locker quotations for all underwriter cards under this comparison deal."""
    try:
        results = generate_all_quotations(db, tenure_id, user.id)
        return {
            "status": "success",
            "tenure_id": tenure_id,
            "generated_count": len(results),
            "quotes": results,
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
@router.post("/{tenure_id}/rescan")
def rescan_comparison(
    tenure_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Force re-extract and rescan all quotation sessions under this comparison tenure."""
    try:
        return rescan_comparison_tenure(db, tenure_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.exception("Failed to rescan comparison tenure %s: %s", tenure_id, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to rescan comparison")


@router.post("/{tenure_id}/upload-previous-policy")
async def upload_previous_policy(
    tenure_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Upload a quotation or schedule PDF specifically for the previous policy year (e.g. 2025)."""
    tenure = db.get(InsuranceTenure, tenure_id)
    if not tenure:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenure not found")

    current_year = tenure.coverage_start_date.year if tenure.coverage_start_date else datetime.now().year
    prev_year = current_year - 1

    year_start = date(prev_year, 1, 1)
    year_end = date(prev_year, 12, 31)

    prev_tenure = db.scalar(
        select(InsuranceTenure)
        .where(
            InsuranceTenure.tracked_vehicle_id == tenure.tracked_vehicle_id,
            InsuranceTenure.coverage_start_date >= year_start,
            InsuranceTenure.coverage_start_date <= year_end,
        )
        .limit(1)
    )

    if not prev_tenure:
        from datetime import timedelta
        st_month = tenure.coverage_start_date.month if tenure.coverage_start_date else 1
        st_day = min(tenure.coverage_start_date.day if tenure.coverage_start_date else 1, 28)
        prev_start = date(prev_year, st_month, st_day)
        prev_end = date(current_year, st_month, st_day) - timedelta(days=1)
        prev_tenure = InsuranceTenure(
            id=new_id(),
            tracked_vehicle_id=tenure.tracked_vehicle_id,
            customer_id=tenure.customer_id,
            vehicle_no=tenure.vehicle_no,
            customer_name=tenure.customer_name,
            coverage_start_date=prev_start,
            coverage_end_date=prev_end,
            status="completed",
            expiry_month=prev_end.strftime("%B"),
            road_tax=float(tenure.road_tax),
            runner_fee=float(tenure.runner_fee),
            sub_agent_name=tenure.sub_agent_name,
        )
        db.add(prev_tenure)
        db.commit()
        db.refresh(prev_tenure)

    idempotency_key = f"prev_comp_{prev_tenure.id}_{new_id()[:12]}"
    try:
        queued = await create_queued_upload(
            db,
            settings,
            owner_id=user.id,
            upload=file,
            idempotency_key=idempotency_key,
            enhanced_reading=False,
            is_test=False,
            tenure_id=prev_tenure.id,
        )
        if queued.session:
            queued.session.tenure_id = prev_tenure.id
            queued.session.is_tenure_active = True
            db.commit()

        return {
            "status": "success",
            "prev_tenure_id": prev_tenure.id,
            "session_id": queued.session.id if queued.session else None,
            "job_id": queued.job.id if queued.job else None,
            "uploaded_file_id": queued.uploaded_file.id if queued.uploaded_file else None,
        }
    except Exception as e:
        logger.exception("Failed to upload previous policy PDF for tenure %s: %s", tenure_id, e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


class UpdateComparisonEntryPatch(BaseModel):
    is_hidden: bool | None = None
    manual_rank: int | None = None
    basic_figure_amount: float | None = None


@router.patch("/{tenure_id}/entries/{entry_id}")
def patch_comparison_entry(
    tenure_id: str,
    entry_id: str,
    payload: UpdateComparisonEntryPatch,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Toggle card visibility (is_hidden), manual rank override, or inline basic figure amount."""
    entry = db.get(TenureComparisonEntry, entry_id)
    if not entry or entry.tenure_id != tenure_id:
        raise HTTPException(status_code=404, detail="Comparison entry not found")
    if payload.is_hidden is not None:
        entry.is_hidden = payload.is_hidden
    if payload.manual_rank is not None:
        entry.manual_rank = payload.manual_rank if payload.manual_rank > 0 else None
    if payload.basic_figure_amount is not None:
        if entry.session_id:
            from sqlalchemy.orm.attributes import flag_modified
            s = db.get(SessionModel, entry.session_id)
            if s and s.draft:
                f = dict(s.draft.fields or {})
                company_lower = (entry.company_name or "").lower()
                is_takaful = any(k in company_lower for k in ("takaful", "etiqa", "stmb", "syarikat takaful"))
                target_key = "basic_contribution" if is_takaful else "basic_premium"
                f[target_key] = {"value": payload.basic_figure_amount}
                s.draft.fields = f
                flag_modified(s.draft, "fields")
    db.commit()

    # Re-rank after modification
    entries = list(db.scalars(select(TenureComparisonEntry).where(TenureComparisonEntry.tenure_id == tenure_id)).all())
    tenure = db.get(InsuranceTenure, tenure_id)
    if tenure:
        if tenure.stage in ("Prospecting", "draft", None):
            tenure.stage = "Quotations"
        record_stage_timestamp(tenure, "Quotations")
    rank_comparison_entries(
        entries,
        explicit_winning_company_id=tenure.winning_company_id if tenure else None,
        explicit_winning_ref=tenure.winning_quotation_ref if tenure else None,
        auto_recommend_rank1=False,
    )
    db.commit()
    return {
        "status": "success",
        "entry_id": entry_id,
        "is_hidden": entry.is_hidden,
        "manual_rank": entry.manual_rank,
        "rank": entry.rank,
    }


@router.post("/{tenure_id}/rerank")
def rerank_deal_entries(
    tenure_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Re-rank visible comparison entries using the 4-tier Best Deal criteria."""
    entries = list(db.scalars(select(TenureComparisonEntry).where(TenureComparisonEntry.tenure_id == tenure_id)).all())
    tenure = db.get(InsuranceTenure, tenure_id)
    ranked = rank_comparison_entries(
        entries,
        explicit_winning_company_id=tenure.winning_company_id if tenure else None,
        explicit_winning_ref=tenure.winning_quotation_ref if tenure else None,
        auto_recommend_rank1=False,
    )
    db.commit()
    return {"status": "success", "ranked_count": len(ranked)}


class ResolveDuplicateRequest(BaseModel):
    action: str | None = Field(None, description="'replace', 'keep', or 'remove'")
    resolution: str | None = None
    original_session_id: str | None = None


@router.post("/{tenure_id}/duplicates/{session_id}/resolve")
def resolve_duplicate_session(
    tenure_id: str,
    session_id: str,
    payload: ResolveDuplicateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Resolve duplicate quote ingestion banner: replace existing, keep as new version, or remove."""
    session = db.get(SessionModel, session_id)
    if not session or session.tenure_id != tenure_id:
        raise HTTPException(status_code=404, detail="Duplicate session not found")

    action = (payload.action or payload.resolution or "").lower()
    if action == "replace":
        session.duplicate_resolution = "replaced"
        session.is_tenure_active = True
        session.status = "active"
        orig_id = payload.original_session_id or session.duplicate_of_session_id
        if orig_id:
            orig_s = db.get(SessionModel, orig_id)
            if orig_s:
                orig_s.is_tenure_active = False
                orig_s.duplicate_resolution = "replaced_by_newer"
        # Update comparison entry session_id if applicable
        entry = db.scalar(
            select(TenureComparisonEntry).where(
                TenureComparisonEntry.tenure_id == tenure_id,
                TenureComparisonEntry.company_name == session.detected_company,
            )
        )
        if entry:
            entry.session_id = session.id
    elif action == "keep":
        session.duplicate_resolution = "kept"
        session.is_tenure_active = True
        session.status = "active"
    elif action == "remove":
        session.duplicate_resolution = "removed"
        session.is_tenure_active = False
        session.status = "trash"
    else:
        raise HTTPException(status_code=400, detail="Invalid action. Must be 'replace', 'keep', or 'remove'.")

    db.commit()
    return {"status": "success", "session_id": session_id, "action": action}
