"""Marketing Comparison API router."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user, settings_dep
from app.auth.rbac import require_role
from app.core.config import Settings
from app.db.session import get_db
from app.services.realtime_hub import publish_realtime_update
from app.models.enums import Role
from app.models.tables import InsuranceCompany, InsuranceTenure, Session as SessionModel, TenureComparisonEntry, UploadedFile, User, new_id
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


from pydantic import field_validator

def _parse_flexible_float(v: Any) -> float | None:
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

def _parse_flexible_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    s = str(v).lower()
    return "yes" in s or "true" in s or "included" in s or "1" in s or "on" in s

class FixedCostsUpdateRequest(BaseModel):
    road_tax: float = Field(0.0, description="Road tax amount in MYR")
    runner_fee: float = Field(0.0, description="Runner / agent service fee in MYR")
    include_road_tax: bool | None = Field(None, description="Whether to include road tax in comparisons and quotations")
    include_runner_fee: bool | None = Field(None, description="Whether to include runner fee in comparisons and quotations")
    windscreen_target: float | None = Field(None, description="Windscreen coverage amount in MYR")
    ncd_percentage: float | None = Field(None, description="NCD percentage (e.g. 55.0)")
    current_ncd: float | None = Field(None, description="Current NCD percentage from previous policy term (e.g. 55.0)")
    coverage_start_date: str | None = Field(None, description="ISO format or YYYY-MM-DD for insurance start date")
    coverage_end_date: str | None = Field(None, description="ISO format or YYYY-MM-DD for insurance end date")
    customer_name: str | None = Field(None, description="Customer name")
    ic_no: str | None = Field(None, description="Malaysian IC or Passport number")
    vehicle_no: str | None = Field(None, description="Vehicle registration plate")
    car_brand: str | None = Field(None, description="Car brand / make (e.g. Honda, Toyota, Proton)")
    engine_cc: str | None = Field(None, description="Engine CC (e.g. 1496 CC)")
    engine_no: str | None = Field(None, description="Engine number")
    chassis_no: str | None = Field(None, description="Chassis / VIN number")
    vehicle_model: str | None = Field(None, description="Vehicle make and model")
    car_model: str | None = Field(None, description="Car model alias")
    vehicle_type: str | None = Field(None, description="Vehicle type (e.g. Car, NonSaloonCar, Lorry, Motorcycle, CompanyCar)")
    manufacture_year: int | None = Field(None, description="Vehicle year of manufacture (e.g. 2020)")
    quotation_discount: float | None = Field(None, description="Global quotation discount in MYR")
    motor_discount_pct: float | None = Field(None, description="Percentage discount applied to motor insurance (0-100%)")

    @field_validator("road_tax", "runner_fee", "windscreen_target", "ncd_percentage", "current_ncd", "quotation_discount", "motor_discount_pct", mode="before")
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
    discount: float | None = None
    windscreen_sum_insured: float | None = None
    special_perils: str | None = None
    llp_llop: str | None = None
    extra_addons: dict[str, str] | None = None
    betterment_rate: float | None = None
    betterment_mode: str | None = None
    is_recommended: bool = False
    is_manual: bool = True
    notes: str | None = None
    basic_figure_amount: float | None = None
    source_quotation_no: str | None = None
    expected_version: int | None = None

    @field_validator("sum_insured", "motor_premium", "excess", "windscreen_sum_insured", "basic_figure_amount", "discount", mode="before")
    def parse_floats(cls, v):
        return _parse_flexible_float(v)

    @field_validator("agreed_value", "waiver_betterment", "is_recommended", "is_manual", mode="before")
    def parse_bools(cls, v):
        return _parse_flexible_bool(v)


class SelectWinnerRequest(BaseModel):
    entry_id: str = Field(..., description="ID of the winning comparison entry")
    force_state: bool | None = Field(None, description="Optional explicit boolean state; if None, toggles current state")


class RoadTaxPreviewRequest(BaseModel):
    capacity: str | float | int | None = None
    unit: str | None = None
    vehicle_type: str = "Car"
    owner_type: str = "Individual"
    jurisdiction: str = "West Malaysia"


@router.post("/calculate-road-tax")
def preview_road_tax(
    payload: RoadTaxPreviewRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Calculate JPJ road tax preview dynamically based on engine capacity (CC, kW, KG) and vehicle type."""
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF, Role.DEV)
    from app.services.road_tax_engine import calculate_road_tax_unified
    try:
        return calculate_road_tax_unified(
            capacity=payload.capacity,
            unit=payload.unit,
            vehicle_type=payload.vehicle_type,
            owner_type=payload.owner_type,
            jurisdiction=payload.jurisdiction,
            db=db,
        )
    except Exception as e:
        logger.exception("Failed to calculate road tax preview: %s", e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


class ToggleFeesRequest(BaseModel):
    include_road_tax: bool | None = None
    include_runner_fee: bool | None = None
    road_tax: float | None = None
    runner_fee: float | None = None
    motor_discount_pct: float | None = None

    @field_validator("road_tax", "runner_fee", "motor_discount_pct", mode="before")
    def parse_toggle_floats(cls, v):
        return _parse_flexible_float(v)


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


@router.post("/{tenure_id}/materialize")
def materialize_comparison(
    tenure_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Idempotently materialize comparison entries for a tenure at write time."""
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF, Role.DEV)
    from app.services.marketing_comparison.materialize import materialize_comparison_entries

    try:
        return materialize_comparison_entries(db, tenure_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.exception("Failed to materialize comparison for tenure %s: %s", tenure_id, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to materialize comparison")


@router.post("/{tenure_id}/refresh-ledger")
def refresh_ledger(
    tenure_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Re-extract customer & vehicle ledger from uploaded quotations via recency waterfall, recalculating road tax dynamically."""
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF, Role.DEV)
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
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF, Role.DEV)
    try:
        res = update_tenure_fixed_costs(
            db,
            tenure_id,
            road_tax=payload.road_tax,
            runner_fee=payload.runner_fee,
            include_road_tax=payload.include_road_tax,
            include_runner_fee=payload.include_runner_fee,
            windscreen_target=payload.windscreen_target,
            ncd_percentage=payload.ncd_percentage,
            current_ncd=payload.current_ncd,
            coverage_start_date=payload.coverage_start_date,
            coverage_end_date=payload.coverage_end_date,
            customer_name=payload.customer_name,
            ic_no=payload.ic_no,
            vehicle_no=payload.vehicle_no,
            car_brand=payload.car_brand,
            engine_cc=payload.engine_cc,
            engine_no=payload.engine_no,
            chassis_no=payload.chassis_no,
            vehicle_model=payload.vehicle_model or payload.car_model,
            vehicle_type=payload.vehicle_type,
            manufacture_year=payload.manufacture_year,
            quotation_discount=payload.quotation_discount,
            motor_discount_pct=payload.motor_discount_pct,
        )
        publish_realtime_update(scope="comparison", resource_id=tenure_id, actor=user, summary="Fixed costs updated", extra_scopes=("ledger",))
        return res

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.exception("Failed to update fixed costs for tenure %s: %s", tenure_id, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update fixed costs")


@router.post("/{tenure_id}/toggle-fees")
def toggle_tenure_fees(
    tenure_id: str,
    payload: ToggleFeesRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Quickly toggle include_road_tax and/or include_runner_fee, or adjust fee amounts."""
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF, Role.DEV)
    tenure = db.get(InsuranceTenure, tenure_id)
    if not tenure:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenure not found")

    rt = payload.road_tax if payload.road_tax is not None else float(tenure.road_tax)
    rf = payload.runner_fee if payload.runner_fee is not None else float(tenure.runner_fee)
    inc_rt = payload.include_road_tax if payload.include_road_tax is not None else (tenure.include_road_tax is not False)
    inc_rf = payload.include_runner_fee if payload.include_runner_fee is not None else (tenure.include_runner_fee is not False)
    if payload.motor_discount_pct is not None and (payload.motor_discount_pct < 0 or payload.motor_discount_pct > 100):
        raise HTTPException(status_code=422, detail="Motor discount percentage must be between 0 and 100%.")

    try:
        res = update_tenure_fixed_costs(
            db,
            tenure_id,
            road_tax=rt,
            runner_fee=rf,
            include_road_tax=inc_rt,
            include_runner_fee=inc_rf,
            motor_discount_pct=payload.motor_discount_pct,
        )
        publish_realtime_update(scope="comparison", resource_id=tenure_id, actor=user, summary="Fees toggled", extra_scopes=("ledger",))
        return res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.exception("Failed to toggle fees for tenure %s: %s", tenure_id, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to toggle fees")


@router.post("/{tenure_id}/entry")
def upsert_entry(
    tenure_id: str,
    payload: ComparisonEntryUpsertRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Create or update an underwriter comparison column."""
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF, Role.DEV)
    try:
        res = save_comparison_entry(db, tenure_id, payload.model_dump())
        publish_realtime_update(scope="comparison", resource_id=tenure_id, actor=user, summary="Comparison entry saved", extra_scopes=("ledger",))
        return res
    except ValueError as e:
        err_msg = str(e)
        if "Concurrent modification conflict" in err_msg:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err_msg)
    except Exception as e:
        logger.exception("Failed to upsert comparison entry for tenure %s: %s", tenure_id, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save entry")


@router.delete("/{tenure_id}/entry/{entry_id}")
def delete_entry(
    tenure_id: str,
    entry_id: str,
    all_versions: bool = Query(default=False, description="Delete all versions of this underwriter"),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Delete a comparison column."""
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF, Role.DEV)
    try:
        res = delete_comparison_entry(db, tenure_id, entry_id, delete_all_versions=all_versions)
        publish_realtime_update(scope="comparison", resource_id=tenure_id, actor=user, summary="Comparison entry deleted", extra_scopes=("ledger",))
        return res
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
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF, Role.DEV)
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
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF, Role.DEV)
    try:
        res = select_winner_and_generate_draft(
            db,
            tenure_id,
            payload.entry_id,
            user.id,
            force_state=payload.force_state,
        )
        publish_realtime_update(scope="comparison", resource_id=tenure_id, actor=user, summary="Winner updated", extra_scopes=("ledger", "sessions"))
        return res
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
    """Generate executive Malaysian WhatsApp teaser text for client messaging (pure read-only)."""
    try:
        teaser_text = format_whatsapp_teaser(db, tenure_id)
        return {"status": "success", "teaser_text": teaser_text}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.exception("Failed to generate WhatsApp teaser for tenure %s: %s", tenure_id, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to format teaser")
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
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF, Role.DEV)
    tenure = db.get(InsuranceTenure, tenure_id)
    if not tenure:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Tenure {tenure_id} not found")

    fname = file.filename or ""
    # Exact duplicate check: if a file with the identical name already exists in this tenure
    existing_file = db.scalar(
        select(UploadedFile)
        .join(SessionModel, SessionModel.uploaded_file_id == UploadedFile.id)
        .where(
            SessionModel.tenure_id == tenure_id,
            SessionModel.status != "trash",
            UploadedFile.original_filename == fname,
        )
    )
    if existing_file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Duplicate quotation: '{fname}' has already been uploaded for this comparison.",
        )

    # Check if filename specifies a year and verify against tenure coverage year (never block for day/month)
    year_match = re.search(r"(?:^|[_\-\s])(20\d{2})(?:[_\-\s]|\.pdf|\d{4})", fname, re.IGNORECASE)
    if year_match and tenure.coverage_start_date:
        file_year = int(year_match.group(1))
        if file_year != tenure.coverage_start_date.year:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot upload: quotation year ({file_year}) does not match comparison year ({tenure.coverage_start_date.year}).",
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
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF, Role.DEV)
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
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF, Role.DEV)
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
class ComparisonRescanRequest(BaseModel):
    session_id: str | None = None
    deep: bool = True


@router.post("/{tenure_id}/rescan")
def rescan_comparison(
    tenure_id: str,
    payload: ComparisonRescanRequest | None = None,
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Force deep re-extract and rescan quotation session(s) under this comparison tenure."""
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF, Role.DEV)
    try:
        return rescan_comparison_tenure(
            db,
            tenure_id,
            user=user,
            settings=settings,
            session_id=payload.session_id if payload else None,
            deep=payload.deep if payload else True,
        )
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
    """Upload a Cover Note or Quotation PDF for the previous policy year, extract everything, and link it in the ledger."""
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF, Role.DEV)
    tenure = db.get(InsuranceTenure, tenure_id)
    if not tenure:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenure not found")

    from dateutil.relativedelta import relativedelta

    current_start = tenure.coverage_start_date or datetime.now(timezone.utc)
    if current_start.tzinfo is None:
        current_start = current_start.replace(tzinfo=timezone.utc)
    prev_year = current_start.year - 1
    year_start = datetime(prev_year, 1, 1, tzinfo=timezone.utc)
    year_end = datetime(prev_year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

    prev_tenure = db.get(InsuranceTenure, tenure.previous_tenure_id) if tenure.previous_tenure_id else None
    if not prev_tenure:
        prev_tenure = db.scalar(
            select(InsuranceTenure)
            .where(
                InsuranceTenure.tracked_vehicle_id == tenure.tracked_vehicle_id,
                InsuranceTenure.id != tenure.id,
                InsuranceTenure.coverage_start_date >= year_start,
                InsuranceTenure.coverage_start_date <= year_end,
                InsuranceTenure.is_discarded == False,
            )
            .order_by(InsuranceTenure.coverage_start_date.desc())
            .limit(1)
        )

    if not prev_tenure:
        prev_start = current_start - relativedelta(years=1)
        prev_end = current_start - relativedelta(days=1)
        prev_tenure = InsuranceTenure(
            id=new_id(),
            tracked_vehicle_id=tenure.tracked_vehicle_id,
            customer_id=tenure.customer_id,
            vehicle_no=tenure.vehicle_no,
            customer_name=tenure.customer_name,
            coverage_start_date=prev_start,
            coverage_end_date=prev_end,
            status="hit",
            stage="Close - Win",
            business_type="Renewal",
            tenure_chain_id=tenure.tenure_chain_id,
            expiry_month=prev_end.strftime("%Y-%m"),
            road_tax=float(tenure.road_tax),
            runner_fee=float(tenure.runner_fee),
            include_road_tax=tenure.include_road_tax,
            include_runner_fee=tenure.include_runner_fee,
            sub_agent_name=tenure.sub_agent_name,
            created_by_id=user.id,
            is_hidden=False,
            is_projected=False,
            is_discarded=False,
        )
        db.add(prev_tenure)
        db.flush()

    if tenure.previous_tenure_id != prev_tenure.id:
        tenure.previous_tenure_id = prev_tenure.id
    if prev_tenure.tenure_chain_id != tenure.tenure_chain_id:
        prev_tenure.tenure_chain_id = tenure.tenure_chain_id
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

        # Run extraction synchronously so Cover Note or Quotation fields & ledger populate immediately
        if queued.job and queued.job.state == "queued":
            try:
                from app.storage.supabase import SupabaseStorage
                from app.workers.extraction_worker import process_extraction_job

                try:
                    storage_inst = SupabaseStorage(settings)
                except Exception:
                    storage_inst = None
                process_extraction_job(
                    db,
                    settings,
                    queued.job,
                    worker_id=f"prev_policy_{new_id()[:8]}",
                    storage=storage_inst,
                )
            except Exception as extract_exc:
                logger.warning("Inline extraction warning for previous policy job %s: %s", queued.job.id, extract_exc)

        # Materialize comparison entry on prev_tenure so Quotations and Cover Notes both populate full fields
        try:
            get_marketing_comparison(db, prev_tenure.id)
        except Exception as mat_exc:
            logger.warning("Could not materialize comparison for prev_tenure %s: %s", prev_tenure.id, mat_exc)

        db.refresh(prev_tenure)
        prev_entries = list(
            db.scalars(
                select(TenureComparisonEntry)
                .where(TenureComparisonEntry.tenure_id == prev_tenure.id)
                .order_by(TenureComparisonEntry.is_recommended.desc(), TenureComparisonEntry.total_payable.asc())
            ).all()
        )
        best_prev = prev_entries[0] if prev_entries else None
        if best_prev:
            if not prev_tenure.winning_company_id and best_prev.company_id:
                prev_tenure.winning_company_id = best_prev.company_id
            if prev_tenure.won_premium is None and float(best_prev.total_payable or 0) > 0:
                prev_tenure.won_premium = float(best_prev.total_payable)
            if not prev_tenure.winning_quotation_ref and getattr(best_prev, "quotation_ref", None):
                prev_tenure.winning_quotation_ref = best_prev.quotation_ref

        if prev_tenure.coverage_end_date:
            prev_tenure.expiry_month = prev_tenure.coverage_end_date.strftime("%Y-%m")
        prev_tenure.status = "hit"
        prev_tenure.stage = "Close - Win"
        prev_tenure.is_hidden = False
        prev_tenure.is_projected = False
        if tenure.ncd_percentage is None and prev_tenure.ncd_percentage is not None:
            tenure.ncd_percentage = prev_tenure.ncd_percentage
        record_stage_timestamp(prev_tenure, "Close - Win")
        db.commit()

        publish_realtime_update(
            scope="comparison",
            resource_id=tenure_id,
            actor=user,
            summary="Previous policy extracted and linked to ledger",
            extra_scopes=("ledger",),
        )
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
    sum_insured: float | None = None
    motor_premium: float | None = None
    agreed_value: bool | None = None
    valuation_type: str | None = None
    waiver_betterment: bool | None = None
    betterment_rate: float | None = None
    betterment_mode: str | None = None
    basic_figure_amount: float | None = None
    towing_limit: str | None = None
    special_perils: str | None = None
    llp_llop: str | None = None
    extra_addons: dict[str, str] | None = None
    excess: float | None = None
    windscreen_sum_insured: float | None = None
    notes: str | None = None
    expected_version: int | None = None
    clear_override_field: str | None = None


@router.patch("/{tenure_id}/entries/{entry_id}")
def patch_comparison_entry(
    tenure_id: str,
    entry_id: str,
    payload: UpdateComparisonEntryPatch,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Inline-edit comparison card fields, visibility, manual rank, or revert a single manual override."""
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF, Role.DEV)
    from sqlalchemy.orm.attributes import flag_modified
    from app.services.marketing_comparison.materialize import (
        get_entry_overrides,
        record_manual_overrides,
    )
    from app.services.marketing_comparison_service import (
        _extract_excess,
        _resolve_comparison_benefits,
    )

    entry = db.get(TenureComparisonEntry, entry_id)
    if not entry or entry.tenure_id != tenure_id:
        raise HTTPException(status_code=404, detail="Comparison entry not found")

    if payload.expected_version is not None:
        curr_ver = entry.version or 1
        if curr_ver != payload.expected_version:
            raise HTTPException(
                status_code=409,
                detail=f"Concurrent modification conflict: entry has version {curr_ver}, expected {payload.expected_version}.",
            )

    # Validate string & numeric bounds
    if payload.towing_limit is not None and len(payload.towing_limit.strip()) > 100:
        raise HTTPException(status_code=422, detail="Towing limit must be 100 characters or fewer.")
    if payload.special_perils is not None and len(payload.special_perils.strip()) > 50:
        raise HTTPException(status_code=422, detail="Special Perils value must be 50 characters or fewer.")
    if payload.llp_llop is not None and len(payload.llp_llop.strip()) > 50:
        raise HTTPException(status_code=422, detail="LLP / LLOP value must be 50 characters or fewer.")
    if payload.notes is not None and len(payload.notes.strip()) > 160:
        raise HTTPException(status_code=422, detail="Notes must be 160 characters or fewer.")
    if payload.excess is not None and payload.excess < 0:
        raise HTTPException(status_code=422, detail="Excess cannot be negative.")
    if payload.windscreen_sum_insured is not None and payload.windscreen_sum_insured < 0:
        raise HTTPException(status_code=422, detail="Windscreen sum insured cannot be negative.")
    if payload.sum_insured is not None and payload.sum_insured < 0:
        raise HTTPException(status_code=422, detail="Sum insured cannot be negative.")
    if payload.motor_premium is not None and payload.motor_premium < 0:
        raise HTTPException(status_code=422, detail="Motor premium cannot be negative.")
    if payload.betterment_rate is not None and (payload.betterment_rate < 0 or payload.betterment_rate > 100):
        raise HTTPException(status_code=422, detail="Betterment rate must be between 0 and 100%.")

    from datetime import datetime, timezone
    from decimal import Decimal
    from app.services.marketing_comparison.dynamic_addons import sanitize_extra_addons_map
    from app.services.marketing_comparison.ncd_evaluator import (
        check_has_betterment_peril,
        evaluate_betterment_rules,
        get_standard_betterment_rate,
    )
    from app.services.marketing_comparison.workspace_sync import sync_session_draft_from_comparison

    tenure = db.get(InsuranceTenure, tenure_id)
    edited_fields: list[str] = []
    clear_field: str | None = payload.clear_override_field.strip() if payload.clear_override_field else None

    # Capture non-overridden PDF-detected baseline values BEFORE applying this edit so reverting back to detected auto-clears Manual
    s_baseline_sess = db.get(SessionModel, entry.session_id) if entry.session_id else None
    detected_baseline: dict[str, Any] = {}
    if s_baseline_sess and s_baseline_sess.draft:
        existing_overrides = set(get_entry_overrides(entry))
        opts_b = dict(s_baseline_sess.draft.display_options or {})
        detected_baseline = dict(opts_b.get("comparison_detected_baseline") or {})
        baseline_dirty = False
        baseline_fields = (
            "sum_insured",
            "motor_premium",
            "agreed_value",
            "valuation_type",
            "waiver_betterment",
            "betterment_rate",
            "towing_limit",
            "special_perils",
            "llp_llop",
            "extra_addons",
            "excess",
            "windscreen_sum_insured",
        )
        for bf in baseline_fields:
            if bf not in existing_overrides and bf not in detected_baseline:
                bval = getattr(entry, bf, None)
                if isinstance(bval, Decimal):
                    bval = float(bval)
                elif isinstance(bval, dict):
                    bval = dict(bval)
                detected_baseline[bf] = bval
                baseline_dirty = True
        if baseline_dirty:
            opts_b["comparison_detected_baseline"] = detected_baseline
            s_baseline_sess.draft.display_options = opts_b
            flag_modified(s_baseline_sess.draft, "display_options")

    if payload.is_hidden is not None:
        entry.is_hidden = payload.is_hidden
    if payload.manual_rank is not None:
        entry.manual_rank = payload.manual_rank if payload.manual_rank > 0 else None

    if payload.sum_insured is not None:
        entry.sum_insured = round(float(payload.sum_insured), 2)
        edited_fields.append("sum_insured")

    if payload.agreed_value is not None or payload.valuation_type is not None:
        if payload.valuation_type is not None:
            is_agreed = payload.valuation_type.strip().lower() in ("agreed value", "agreed_value")
        else:
            is_agreed = bool(payload.agreed_value)
        entry.agreed_value = is_agreed
        entry.valuation_type = "agreed_value" if is_agreed else "market_value"
        edited_fields.extend(["agreed_value", "valuation_type"])

    b_mode = (payload.betterment_mode or "").strip().lower()
    if b_mode == "auto":
        clear_field = "waiver_betterment"
    elif payload.betterment_rate is not None:
        b_rate_val = round(float(payload.betterment_rate), 2)
        entry.waiver_betterment = b_rate_val == 0.0
        entry.betterment_rate = b_rate_val
        entry.betterment_display = (
            "No (0%)"
            if b_rate_val == 0.0
            else f"Yes ({int(b_rate_val) if float(b_rate_val).is_integer() else b_rate_val}%)"
        )
        edited_fields.extend(["waiver_betterment", "betterment_rate"])
    elif payload.waiver_betterment is not None or b_mode in ("waived", "copay"):
        waived_flag = (b_mode == "waived") if b_mode in ("waived", "copay") else bool(payload.waiver_betterment)
        entry.waiver_betterment = waived_flag
        if entry.waiver_betterment:
            entry.betterment_rate = 0.0
            entry.betterment_display = "No (0%)"
        else:
            veh_yom = getattr(tenure.tracked_vehicle, "manufacture_year", None) if (tenure and getattr(tenure, "tracked_vehicle", None)) else None
            quote_year = tenure.coverage_start_date.year if (tenure and tenure.coverage_start_date) else datetime.now(timezone.utc).year
            veh_age = max(0, quote_year - (veh_yom or quote_year))
            b_rate, b_disp = get_standard_betterment_rate(veh_age)
            entry.betterment_rate = b_rate
            entry.betterment_display = b_disp
        edited_fields.append("waiver_betterment")

    if payload.extra_addons is not None:
        cleaned_ea = sanitize_extra_addons_map(payload.extra_addons)
        entry.extra_addons = {**dict(getattr(entry, "extra_addons", None) or {}), **cleaned_ea}
        flag_modified(entry, "extra_addons")
        edited_fields.append("extra_addons")

    if payload.motor_premium is not None:
        entry.motor_premium = round(float(payload.motor_premium), 2)
        edited_fields.append("motor_premium")

    if payload.towing_limit is not None:
        clean_tow = payload.towing_limit.strip()
        if clean_tow.lower() in {"0", "0.0", "0 km", "rm 0", "no towing", "without towing", "not included", "none", "tiada", "nil"}:
            entry.towing_limit = "No towing"
            entry.towing_km = "No towing"
            edited_fields.append("towing_limit")
        elif clean_tow:
            entry.towing_limit = clean_tow
            entry.towing_km = clean_tow
            edited_fields.append("towing_limit")
        else:
            clear_field = "towing_limit"

    if payload.special_perils is not None:
        clean_sp = payload.special_perils.strip()
        if clean_sp.lower() in {"not included", "no", "none", "excluded", "-"}:
            entry.special_perils = None
            edited_fields.append("special_perils")
        elif clean_sp:
            entry.special_perils = clean_sp
            edited_fields.append("special_perils")
        else:
            entry.special_perils = None
            clear_field = "special_perils"

    if payload.llp_llop is not None:
        clean_llp = payload.llp_llop.strip()
        if clean_llp.lower() in {"not included", "no", "none", "excluded", "-"}:
            entry.llp_llop = None
            edited_fields.append("llp_llop")
        elif clean_llp:
            entry.llp_llop = clean_llp
            edited_fields.append("llp_llop")
        else:
            entry.llp_llop = None
            clear_field = "llp_llop"

    if payload.excess is not None:
        entry.excess = float(payload.excess)
        edited_fields.append("excess")

    if payload.windscreen_sum_insured is not None:
        entry.windscreen_sum_insured = float(payload.windscreen_sum_insured) if payload.windscreen_sum_insured > 0 else None
        edited_fields.append("windscreen_sum_insured")

    if payload.notes is not None:
        clean_notes = payload.notes.strip()
        entry.notes = clean_notes or None
        if clean_notes:
            edited_fields.append("notes")
        else:
            clear_field = "notes"

    if payload.basic_figure_amount is not None:
        edited_fields.append("basic_figure_amount")
        if entry.session_id:
            s = db.get(SessionModel, entry.session_id)
            if s and s.draft:
                f = dict(s.draft.fields or {})
                company_lower = (entry.company_name or "").lower()
                is_takaful = any(k in company_lower for k in ("takaful", "etiqa", "stmb", "syarikat takaful"))
                target_key = "basic_contribution" if is_takaful else "basic_premium"
                f[target_key] = {"value": payload.basic_figure_amount}
                s.draft.fields = f
                flag_modified(s.draft, "fields")

    # If a field override is cleared, restore its extracted value from the linked session if available
    if clear_field and entry.session_id:
        s_rev = db.get(SessionModel, entry.session_id)
        if s_rev:
            f_rev = dict(s_rev.draft.fields or {}) if s_rev.draft and isinstance(s_rev.draft.fields, dict) else {}
            # Clear manual_override status in draft.fields for the reverted field
            draft_keys_map = {
                "towing_limit": ("towing", "towing_limit"),
                "special_perils": ("special_perils",),
                "llp_llop": ("llp_llop",),
                "excess": ("excess", "excess_amount"),
                "windscreen_sum_insured": ("windscreen_sum_insured", "windscreen"),
            }
            for dk in draft_keys_map.get(clear_field, ()):
                if isinstance(f_rev.get(dk), dict) and f_rev[dk].get("status") == "manual_override":
                    f_rev.pop(dk, None)
            if s_rev.draft:
                s_rev.draft.fields = f_rev
                flag_modified(s_rev.draft, "fields")
            b_rev = _resolve_comparison_benefits(
                db,
                s_rev,
                getattr(s_rev, "company_id", None) or entry.company_id,
                f_rev,
                float(tenure.windscreen_target) if (tenure and tenure.windscreen_target) else None,
            )
            if clear_field in ("towing_limit", "towing_km"):
                entry.towing_limit = b_rev.get("towing_km") or "Unlimited"
                entry.towing_km = entry.towing_limit
            elif clear_field == "special_perils":
                entry.special_perils = b_rev.get("special_perils")
            elif clear_field == "llp_llop":
                entry.llp_llop = b_rev.get("llp_llop")
            elif clear_field == "extra_addons":
                entry.extra_addons = dict(b_rev.get("extra_addons") or {})
                flag_modified(entry, "extra_addons")
            elif clear_field in ("waiver_betterment", "betterment_rate"):
                if isinstance(f_rev.get("waiver_of_betterment"), dict) and f_rev["waiver_of_betterment"].get("status") == "manual_override":
                    f_rev.pop("waiver_of_betterment", None)
                if isinstance(f_rev.get("betterment_rate"), dict):
                    f_rev.pop("betterment_rate", None)
                if s_rev.draft:
                    s_rev.draft.fields = f_rev
                    flag_modified(s_rev.draft, "fields")
                veh_yom = getattr(tenure.tracked_vehicle, "manufacture_year", None) if (tenure and getattr(tenure, "tracked_vehicle", None)) else None
                quote_year = tenure.coverage_start_date.year if (tenure and tenure.coverage_start_date) else datetime.now(timezone.utc).year
                has_p = check_has_betterment_peril(f_rev, b_rev.get("combined_text", ""))
                comp_obj = db.get(InsuranceCompany, s_rev.company_id) if getattr(s_rev, "company_id", None) else None
                w_auto, r_auto, d_auto = evaluate_betterment_rules(
                    yom=veh_yom,
                    quote_year=quote_year,
                    company_name=entry.company_name,
                    has_betterment_peril=has_p,
                    coverage_start_date=tenure.coverage_start_date if tenure else None,
                    company_obj=comp_obj,
                )
                entry.waiver_betterment = w_auto
                entry.betterment_rate = r_auto
                entry.betterment_display = d_auto
            elif clear_field == "windscreen_sum_insured":
                entry.windscreen_sum_insured = b_rev.get("windscreen_sum_insured")
            elif clear_field == "excess":
                entry.excess = _extract_excess(f_rev, s_obj=s_rev)
            elif clear_field == "notes":
                entry.notes = None
    elif clear_field:
        if clear_field == "special_perils":
            entry.special_perils = None
        elif clear_field == "llp_llop":
            entry.llp_llop = None
        elif clear_field == "extra_addons":
            entry.extra_addons = {}
            flag_modified(entry, "extra_addons")
        elif clear_field in ("waiver_betterment", "betterment_rate"):
            veh_yom = getattr(tenure.tracked_vehicle, "manufacture_year", None) if (tenure and getattr(tenure, "tracked_vehicle", None)) else None
            quote_year = tenure.coverage_start_date.year if (tenure and tenure.coverage_start_date) else datetime.now(timezone.utc).year
            w_auto, r_auto, d_auto = evaluate_betterment_rules(
                yom=veh_yom,
                quote_year=quote_year,
                company_name=entry.company_name,
                has_betterment_peril=False,
                coverage_start_date=tenure.coverage_start_date if tenure else None,
            )
            entry.waiver_betterment = w_auto
            entry.betterment_rate = r_auto
            entry.betterment_display = d_auto
        elif clear_field == "notes":
            entry.notes = None

    auto_cleared_fields: list[str] = []
    if edited_fields and detected_baseline:
        def _norm_opt_text(val: Any) -> str:
            s = str(val or "").strip().lower()
            return "" if s in {"", "-", "—", "none", "nil", "no", "not included", "not covered", "tiada"} else s

        def _matches_detected_val(fk: str, cur_val: Any, base_val: Any) -> bool:
            if fk in ("sum_insured", "motor_premium", "excess", "windscreen_sum_insured", "betterment_rate"):
                return abs(float(cur_val or 0.0) - float(base_val or 0.0)) < 0.01
            if fk in ("agreed_value", "waiver_betterment"):
                return bool(cur_val) == bool(base_val)
            if fk in ("special_perils", "llp_llop"):
                return _norm_opt_text(cur_val) == _norm_opt_text(base_val)
            if fk in ("towing_limit", "valuation_type"):
                return str(cur_val or "").strip().lower() == str(base_val or "").strip().lower()
            if fk == "extra_addons":
                c_map = {str(k): str(v) for k, v in (cur_val or {}).items() if str(v).strip().lower() == "yes"}
                b_map = {str(k): str(v) for k, v in (base_val or {}).items() if str(v).strip().lower() == "yes"}
                return c_map == b_map
            return False

        remaining_edited: list[str] = []
        for ef in edited_fields:
            if ef in detected_baseline and _matches_detected_val(ef, getattr(entry, ef, None), detected_baseline[ef]):
                if ef not in auto_cleared_fields:
                    auto_cleared_fields.append(ef)
            else:
                remaining_edited.append(ef)
        if "agreed_value" in auto_cleared_fields and "valuation_type" not in auto_cleared_fields:
            auto_cleared_fields.append("valuation_type")
        if "valuation_type" in auto_cleared_fields and "agreed_value" not in auto_cleared_fields:
            auto_cleared_fields.append("agreed_value")
        if "waiver_betterment" in auto_cleared_fields and "betterment_rate" not in auto_cleared_fields:
            auto_cleared_fields.append("betterment_rate")
        if "betterment_rate" in auto_cleared_fields and "waiver_betterment" not in auto_cleared_fields:
            auto_cleared_fields.append("waiver_betterment")
        edited_fields = [f for f in remaining_edited if f not in auto_cleared_fields]

    sync_fields = list(dict.fromkeys([*edited_fields, *auto_cleared_fields]))

    if edited_fields or clear_field or auto_cleared_fields:
        record_manual_overrides(
            entry,
            edited_fields=edited_fields,
            clear_field=clear_field,
        )
        for cf in auto_cleared_fields:
            record_manual_overrides(entry, clear_field=cf)
        if b_mode == "auto":
            record_manual_overrides(entry, clear_field="betterment_rate")
        entry.version = (entry.version or 1) + 1

    # Sync edited fields & benefits bidirectionally to linked QuotationDraft
    if sync_fields and entry.session_id:
        prem_delta_dec = sync_session_draft_from_comparison(
            db,
            tenure,
            entry.session_id,
            edited_fields=sync_fields,
            field_values={
                "sum_insured": entry.sum_insured,
                "motor_premium": entry.motor_premium,
                "agreed_value": entry.agreed_value,
                "valuation_type": entry.valuation_type,
                "waiver_betterment": entry.waiver_betterment,
                "betterment_rate": float(entry.betterment_rate) if entry.betterment_rate is not None else None,
                "towing_limit": entry.towing_limit,
                "special_perils": entry.special_perils or "Not Included",
                "llp_llop": entry.llp_llop or "Not Included",
                "extra_addons": getattr(entry, "extra_addons", None) or {},
                "excess": entry.excess,
                "windscreen_sum_insured": entry.windscreen_sum_insured,
            },
            explicit_motor_premium=("motor_premium" in sync_fields),
            user_id=user.id if getattr(user, "id", None) else None,
        )
        if prem_delta_dec != Decimal("0.00") and "motor_premium" not in sync_fields:
            entry.motor_premium = round(max(0.0, float(entry.motor_premium or 0.0) + float(prem_delta_dec)), 2)

        if auto_cleared_fields and s_baseline_sess and s_baseline_sess.draft and isinstance(s_baseline_sess.draft.fields, dict):
            draft_clear_map = {
                "sum_insured": ("sum_insured", "coverage_amount"),
                "motor_premium": ("motor_premium", "premium", "premium_due"),
                "agreed_value": ("valuation_type",),
                "valuation_type": ("valuation_type",),
                "towing_limit": ("towing", "towing_limit"),
                "special_perils": ("special_perils",),
                "llp_llop": ("llp_llop",),
                "waiver_betterment": ("waiver_of_betterment",),
                "betterment_rate": ("betterment_rate",),
                "excess": ("excess", "excess_amount"),
                "windscreen_sum_insured": ("windscreen_sum_insured", "windscreen"),
                "extra_addons": ("extra_addons",),
            }
            df_clean = dict(s_baseline_sess.draft.fields)
            df_touched = False
            for cf in auto_cleared_fields:
                for dk in draft_clear_map.get(cf, ()):
                    if isinstance(df_clean.get(dk), dict) and df_clean[dk].get("status") == "manual_override":
                        df_clean[dk] = {**df_clean[dk], "status": "ready"}
                        df_touched = True
            if df_touched:
                s_baseline_sess.draft.fields = df_clean
                flag_modified(s_baseline_sess.draft, "fields")

    eff_rt = float(tenure.road_tax) if (tenure and tenure.include_road_tax is not False) else 0.0
    eff_rf = float(tenure.runner_fee) if (tenure and tenure.include_runner_fee is not False) else 0.0
    entry.road_tax = eff_rt
    entry.runner_fee = eff_rf
    entry.include_road_tax = (tenure.include_road_tax is not False) if tenure else True
    entry.include_runner_fee = (tenure.include_runner_fee is not False) if tenure else True
    entry.total_payable = round(float(entry.motor_premium or 0.0) + eff_rt + eff_rf, 2)
    if float(entry.sum_insured or 0.0) > 0 and float(entry.motor_premium or 0.0) > 0:
        entry.rate_percentage = round((float(entry.motor_premium) / float(entry.sum_insured)) * 100, 4)
    else:
        entry.rate_percentage = 0.0
    if tenure and tenure.covernote_session_id and entry.session_id == tenure.covernote_session_id:
        from app.domain.motor.discount_calculator import calculate_motor_discount

        flat_disc = entry.discount if entry.discount is not None else getattr(tenure, "quotation_discount", 0.0)
        disc_bd = calculate_motor_discount(
            entry.motor_premium,
            getattr(tenure, "motor_discount_pct", 0.0),
            flat_disc,
        )
        tenure.won_premium = float(disc_bd.net_total_payable(eff_rt, eff_rf))

    db.commit()

    # Re-rank after modification
    entries = list(db.scalars(select(TenureComparisonEntry).where(TenureComparisonEntry.tenure_id == tenure_id)).all())
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
    publish_realtime_update(scope="comparison", resource_id=tenure_id, actor=user, summary="Comparison entry updated", extra_scopes=("ledger",))
    return {
        "status": "success",
        "entry_id": entry_id,
        "is_hidden": entry.is_hidden,
        "manual_rank": entry.manual_rank,
        "rank": entry.rank,
        "version": entry.version or 1,
        "sum_insured": float(entry.sum_insured or 0.0),
        "motor_premium": float(entry.motor_premium or 0.0),
        "total_payable": float(entry.total_payable or 0.0),
        "rate_percentage": float(entry.rate_percentage or 0.0),
        "agreed_value": entry.agreed_value,
        "valuation_type": entry.valuation_type,
        "waiver_betterment": entry.waiver_betterment,
        "betterment_rate": float(entry.betterment_rate or 0.0),
        "betterment_display": entry.betterment_display,
        "towing_limit": entry.towing_limit,
        "towing_km": entry.towing_limit if "towing_limit" in get_entry_overrides(entry) else (entry.towing_km or entry.towing_limit),
        "special_perils": entry.special_perils,
        "llp_llop": entry.llp_llop,
        "extra_addons": getattr(entry, "extra_addons", None) or {},
        "betterment_is_auto": not any(
            k in get_entry_overrides(entry) for k in ("waiver_betterment", "betterment_rate")
        ),
        "excess": float(entry.excess or 0.0),
        "windscreen_sum_insured": float(entry.windscreen_sum_insured) if entry.windscreen_sum_insured else None,
        "notes": entry.notes,
        "is_manual": entry.is_manual,
        "manual_overrides": get_entry_overrides(entry),
    }


@router.post("/{tenure_id}/rerank")
def rerank_deal_entries(
    tenure_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Re-rank visible comparison entries using Underwriter Value & Logical Risk Analysis."""
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF, Role.DEV)
    from app.domain.motor.winner_ranking_rules import evaluate_logical_value_rerank

    entries = list(db.scalars(select(TenureComparisonEntry).where(TenureComparisonEntry.tenure_id == tenure_id)).all())
    ranked = evaluate_logical_value_rerank(entries)
    db.commit()
    publish_realtime_update(scope="comparison", resource_id=tenure_id, actor=user, summary="Comparison entry updated", extra_scopes=("ledger",))
    return {
        "status": "success",
        "ranked_count": len(ranked),
        "explanations": {e.id: e.notes for e in ranked if not getattr(e, "is_hidden", False)},
    }


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
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF, Role.DEV)
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
        # Re-sync and materialize all active comparison entries so replaced quote numbers/benefits update atomically
        db.commit()
        from app.services.marketing_comparison.materialize import materialize_comparison_entries

        materialize_comparison_entries(db, tenure_id)
        return {"status": "success", "session_id": session_id, "action": action}
    elif action == "keep":
        session.duplicate_resolution = "kept"
        session.is_tenure_active = True
        session.status = "active"
        db.commit()
        from app.services.marketing_comparison.materialize import materialize_comparison_entries

        materialize_comparison_entries(db, tenure_id)
        return {"status": "success", "session_id": session_id, "action": action}
    elif action == "remove":
        session.duplicate_resolution = "removed"
        session.is_tenure_active = False
        session.status = "trash"
    else:
        raise HTTPException(status_code=400, detail="Invalid action. Must be 'replace', 'keep', or 'remove'.")

    db.commit()
    return {"status": "success", "session_id": session_id, "action": action}


class ConvertDocumentTypeRequest(BaseModel):
    document_type: str = Field(..., description="'covernote' or 'quotation'")


@router.post("/{tenure_id}/sessions/{session_id}/convert-type")
def convert_session_document_type(
    tenure_id: str,
    session_id: str,
    payload: ConvertDocumentTypeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Toggle a session between Cover Note (Issued Policy) and Quotation."""
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF, Role.DEV)
    tenure = db.get(InsuranceTenure, tenure_id)
    if not tenure:
        raise HTTPException(status_code=404, detail="Tenure not found")
    session = db.get(SessionModel, session_id)
    if not session or session.tenure_id != tenure_id:
        raise HTTPException(status_code=404, detail="Session not found under this tenure")

    target_type = payload.document_type.lower().strip()
    if target_type not in ("covernote", "quotation"):
        raise HTTPException(status_code=400, detail="Invalid document_type. Must be 'covernote' or 'quotation'.")

    session.document_type = target_type

    if target_type == "covernote":
        # Remove any existing comparison entry for this session
        entries = list(
            db.scalars(
                select(TenureComparisonEntry).where(
                    TenureComparisonEntry.tenure_id == tenure_id,
                    TenureComparisonEntry.session_id == session.id,
                )
            ).all()
        )
        for e in entries:
            db.delete(e)

        # Bind as the active cover note for the tenure
        tenure.covernote_session_id = session.id
        if session.coverage_start_date:
            tenure.coverage_start_date = session.coverage_start_date
        if session.coverage_end_date:
            tenure.coverage_end_date = session.coverage_end_date
            tenure.expiry_month = session.coverage_end_date.strftime("%Y-%m")
        if getattr(session, "company_id", None):
            tenure.winning_company_id = session.company_id
        if session.policy_number:
            tenure.policy_number = session.policy_number
        if session.draft and isinstance(session.draft.fields, dict):
            tot_val = (session.draft.fields.get("total_amount") or {}).get("value") or (session.draft.fields.get("total_payable") or {}).get("value")
            if tot_val:
                try:
                    tenure.won_premium = float(str(tot_val).replace(",", "").replace("RM", "").strip())
                except (ValueError, TypeError):
                    pass

        if tenure.stage in ("Quotations", "Material to Client", None, "draft"):
            tenure.stage = "Issue Policy"
            stage_hist = dict(tenure.stage_history or {})
            stage_hist["Issue Policy"] = datetime.now(timezone.utc).isoformat()
            tenure.stage_history = stage_hist
            tenure.stage_updated_at = datetime.now(timezone.utc)

        # Autonomous Next-Year Renewal Invariant
        from app.services.insurance_tenure_service import create_next_year_renewal_tenure
        try:
            create_next_year_renewal_tenure(db=db, tenure=tenure, user_id=user.id)
        except Exception:
            pass
    else:
        # Revert back to quotation: clear covernote link if this was the covernote
        if tenure.covernote_session_id == session.id:
            tenure.covernote_session_id = None
        if tenure.stage == "Issue Policy":
            tenure.stage = "Quotations"
            tenure.stage_updated_at = datetime.now(timezone.utc)
        from app.services.insurance_tenure_service import remove_auto_created_next_year_tenure
        try:
            remove_auto_created_next_year_tenure(db=db, tenure=tenure)
        except Exception:
            pass

    db.commit()
    publish_realtime_update(scope="comparison", resource_id=tenure_id, actor=user, summary="Document type converted", extra_scopes=("ledger", "sessions"))
    return {"status": "success", "session_id": session_id, "document_type": target_type}


@router.delete("/{tenure_id}/covernote")
def unlink_tenure_covernote(
    tenure_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Unlink the active Cover Note from the tenure without deleting the session/file."""
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF, Role.DEV)
    tenure = db.get(InsuranceTenure, tenure_id)
    if not tenure:
        raise HTTPException(status_code=404, detail="Tenure not found")

    if tenure.covernote_session_id:
        cn_s = db.get(SessionModel, tenure.covernote_session_id)
        if cn_s:
            cn_s.document_type = "unlinked_covernote"
        tenure.covernote_session_id = None

    other_cns = db.query(SessionModel).filter(
        SessionModel.tenure_id == tenure.id,
        SessionModel.document_type == "covernote"
    ).all()
    for s in other_cns:
        s.document_type = "unlinked_covernote"

    if tenure.stage in ("Issue Policy", "Close - Win"):
        tenure.stage = "Quotations"
        tenure.stage_updated_at = datetime.now(timezone.utc)
    if tenure.status == "hit":
        tenure.status = "draft"
    tenure.won_premium = None

    from app.services.insurance_tenure_service import remove_auto_created_next_year_tenure
    try:
        remove_auto_created_next_year_tenure(db=db, tenure=tenure)
    except Exception:
        pass

    db.commit()
    publish_realtime_update(scope="comparison", resource_id=tenure_id, actor=user, summary="Cover note unlinked", extra_scopes=("ledger",))
    return {"status": "success", "tenure_id": tenure_id, "message": "Cover note unlinked successfully"}


class LinkCovernoteRequest(BaseModel):
    session_id: str


@router.post("/{tenure_id}/covernote/link")
def link_tenure_covernote(
    tenure_id: str,
    payload: LinkCovernoteRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Link a previously unlinked or available Cover Note session to the tenure."""
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF, Role.DEV)
    tenure = db.get(InsuranceTenure, tenure_id)
    if not tenure:
        raise HTTPException(status_code=404, detail="Tenure not found")

    sess = db.get(SessionModel, payload.session_id)
    if not sess or sess.tenure_id != tenure_id:
        raise HTTPException(status_code=404, detail="Session not found or does not belong to this tenure")

    sess.document_type = "covernote"
    tenure.covernote_session_id = sess.id
    tenure.stage = "Issue Policy"
    tenure.stage_updated_at = datetime.now(timezone.utc)

    from app.services.insurance_tenure_service import create_next_year_renewal_tenure
    try:
        create_next_year_renewal_tenure(db=db, tenure=tenure, user_id=user.id)
    except Exception:
        pass

    db.commit()
    publish_realtime_update(scope="comparison", resource_id=tenure_id, actor=user, summary="Cover note linked", extra_scopes=("ledger",))
    return {"status": "success", "tenure_id": tenure_id, "session_id": sess.id, "message": "Policy linked successfully"}


class CovernotePatchRequest(BaseModel):
    policy_number: str | None = None
    company_id: str | None = None
    company_name: str | None = None
    coverage_start_date: str | None = None
    coverage_end_date: str | None = None
    sum_insured: float | None = None
    motor_premium: float | None = None
    total_payable: float | None = None
    road_tax: float | None = None
    runner_fee: float | None = None
    include_road_tax: bool | None = None
    include_runner_fee: bool | None = None
    vehicle_model: str | None = None
    manufacture_year: int | None = None
    agreed_value: bool | None = None
    valuation_type: str | None = None
    windscreen_sum_insured: float | None = None
    towing_limit: str | None = None
    special_perils: str | None = None
    llp_llop: str | None = None
    extra_addons: dict[str, str] | None = None
    included_perils: list[str] | None = None
    excess: float | None = None
    waiver_betterment: bool | None = None
    betterment_rate: float | None = None
    betterment_mode: str | None = None


@router.patch("/{tenure_id}/covernote")
def patch_tenure_covernote(
    tenure_id: str,
    payload: CovernotePatchRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Edit Cover Note policy number, insurer, dates, financials, perils, vehicle specs, and benefits inline or via modal."""
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF, Role.DEV)
    if payload.sum_insured is not None and payload.sum_insured < 0:
        raise HTTPException(status_code=422, detail="Sum insured cannot be negative.")
    if payload.motor_premium is not None and payload.motor_premium < 0:
        raise HTTPException(status_code=422, detail="Motor premium cannot be negative.")
    if payload.total_payable is not None and payload.total_payable < 0:
        raise HTTPException(status_code=422, detail="Total payable cannot be negative.")
    if payload.road_tax is not None and payload.road_tax < 0:
        raise HTTPException(status_code=422, detail="Road tax cannot be negative.")
    if payload.runner_fee is not None and payload.runner_fee < 0:
        raise HTTPException(status_code=422, detail="Runner fee cannot be negative.")
    if payload.betterment_rate is not None and (payload.betterment_rate < 0 or payload.betterment_rate > 100):
        raise HTTPException(status_code=422, detail="Betterment rate must be between 0 and 100%.")
    if payload.manufacture_year is not None and (payload.manufacture_year < 1900 or payload.manufacture_year > 2100):
        raise HTTPException(status_code=422, detail="Manufacture year must be a valid 4-digit year.")
    if payload.excess is not None and payload.excess < 0:
        raise HTTPException(status_code=422, detail="Excess cannot be negative.")
    if payload.windscreen_sum_insured is not None and payload.windscreen_sum_insured < 0:
        raise HTTPException(status_code=422, detail="Windscreen sum insured cannot be negative.")
    if payload.policy_number is not None and len(payload.policy_number.strip()) > 120:
        raise HTTPException(status_code=422, detail="Policy number must be 120 characters or fewer.")

    from app.services.marketing_comparison.covernote_sync import sync_and_update_covernote

    data = payload.model_dump(exclude_unset=True)
    try:
        res = sync_and_update_covernote(
            db,
            tenure_id,
            data,
            user_id=user.id if getattr(user, "id", None) else None,
        )
        publish_realtime_update(scope="comparison", resource_id=tenure_id, actor=user, summary="Cover note updated", extra_scopes=("ledger",))
        return res
    except ValueError as exc:
        msg = str(exc)
        code = 404 if "not found" in msg.lower() or "no active cover note" in msg.lower() else 422
        raise HTTPException(status_code=code, detail=msg)

