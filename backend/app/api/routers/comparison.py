"""Marketing Comparison API router."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import current_user, settings_dep
from app.core.config import Settings
from app.db.session import get_db
from app.models.tables import InsuranceTenure, User, new_id
from app.services.marketing_comparison_service import (
    delete_comparison_entry,
    format_whatsapp_teaser,
    generate_all_quotations,
    generate_quotation_for_entry,
    get_marketing_comparison,
    save_comparison_entry,
    select_winner_and_generate_draft,
    update_tenure_fixed_costs,
)
from app.services.upload_intake_service import create_queued_upload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/comparison", tags=["marketing-comparison"])


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
    except Exception as e:
        logger.exception("Failed to generate all quotes for tenure %s: %s", tenure_id, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate all quotes")
