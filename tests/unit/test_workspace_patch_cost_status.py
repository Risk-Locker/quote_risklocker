"""Unit tests for CostStatus normalization and workspace patch vehicle / fee synchronization."""

from __future__ import annotations

import pytest
from app.domain.benefits import CostStatus, normalize_cost_status
from app.extraction.draft_mapper import normalize_vehicle_model_text


def test_normalize_cost_status_standard_values():
    assert normalize_cost_status("included") == CostStatus.INCLUDED
    assert normalize_cost_status("paid") == CostStatus.PAID
    assert normalize_cost_status("foc") == CostStatus.FOC
    assert normalize_cost_status("unknown") == CostStatus.UNKNOWN


def test_normalize_cost_status_aliases():
    # Frontend sends "optional" when unchecking an add-on
    assert normalize_cost_status("optional") == CostStatus.PAID
    assert normalize_cost_status("extra") == CostStatus.PAID
    assert normalize_cost_status("free") == CostStatus.FOC
    assert normalize_cost_status("waived") == CostStatus.FOC
    assert normalize_cost_status("built_in") == CostStatus.INCLUDED


def test_normalize_cost_status_fallback():
    assert normalize_cost_status(None, default=CostStatus.PAID) == CostStatus.PAID
    assert normalize_cost_status("", default=CostStatus.UNKNOWN) == CostStatus.UNKNOWN
    assert normalize_cost_status("invalid_junk", default=CostStatus.PAID) == CostStatus.PAID


def test_normalize_vehicle_model_deduplication():
    # User entered full name "HONDA CRF250" with brand "HONDA"
    assert normalize_vehicle_model_text("HONDA CRF250", "HONDA") == "HONDA CRF250"
    assert normalize_vehicle_model_text("CRF250", "HONDA") == "HONDA CRF250"
    assert normalize_vehicle_model_text("HONDA HONDA CRF250", "HONDA") == "HONDA CRF250"


from types import SimpleNamespace
from app.models.enums import RecordStatus
from app.models.tables import DraftBenefitSelection, InsuranceTenure, QuotationDraft, Session, TrackedVehicle
from app.services.workspace_patch_service import apply_workspace_patch


class Scalars:
    def __init__(self, rows): self.rows = rows
    def all(self): return list(self.rows)
    def first(self): return self.rows[0] if self.rows else None


class FakeDb:
    def __init__(self, values):
        self.values = {(type(item), item.id): item for item in values}
        self.added = []
        self.commits = 0
        self.rollbacks = 0
        self.refreshed = []

    def get(self, model, object_id): return self.values.get((model, object_id))

    def scalars(self, statement):
        entity = statement.column_descriptions[0].get("entity") if statement.column_descriptions else None
        rows = [item for (model, _id), item in self.values.items() if model is entity]
        return Scalars(rows)

    def scalar(self, statement):
        rows = self.scalars(statement).all()
        return rows[0] if rows else None

    def add(self, item):
        self.added.append(item)
        if getattr(item, "id", None): self.values[(type(item), item.id)] = item

    def delete(self, item): self.values.pop((type(item), item.id), None)
    def flush(self): return None
    def commit(self): self.commits += 1
    def rollback(self): self.rollbacks += 1
    def refresh(self, item): self.refreshed.append(item)


def test_apply_workspace_patch_accepts_optional_cost_status():
    """Verify benefit_update with cost_status='optional' succeeds and normalizes to 'paid'."""
    draft = QuotationDraft(
        id="draft-1",
        revision=3,
        fields={"car_model": {"value": "HONDA CRF250", "status": "ready"}},
        scalar_decisions={},
        warnings=[],
        status=RecordStatus.READY.value,
        display_options={},
    )
    selection = DraftBenefitSelection(
        id="sel-windscreen",
        draft_id="draft-1",
        selection_key="addon:windscreen",
        item_kind="custom",
        state="current",
        cost_status="paid",
        label_override="Windscreen Coverage",
    )
    db = FakeDb([draft, selection])
    user = SimpleNamespace(id="staff-1", role="staff")

    # Client unchecks windscreen, sending cost_status: "optional" and state: "available_addon"
    res = apply_workspace_patch(
        db,
        user,
        "draft-1",
        base_revision=3,
        operations=[{
            "op": "benefit_update",
            "selection_id": "sel-windscreen",
            "state": "available_addon",
            "cost_status": "optional",
        }],
    )

    assert res["revision"] == 4
    assert selection.state == "available_addon"
    assert selection.cost_status == "paid"


def test_apply_workspace_patch_syncs_car_model_and_road_tax_flags_to_tenure():
    """Verify vehicle details and road tax flags synchronize bidirectionally to linked tenure."""
    tv = TrackedVehicle(id="tv-1", vehicle_no="W1234A", car_brand="HONDA", car_model="OLD MODEL")
    tenure = InsuranceTenure(
        id="tenure-1",
        vehicle_no="W1234A",
        tracked_vehicle_id=tv.id,
        customer_name="Ahmad",
        include_road_tax=True,
        include_runner_fee=True,
    )
    tenure.tracked_vehicle = tv
    draft = QuotationDraft(
        id="draft-1",
        revision=3,
        fields={
            "car_model": {"value": "HONDA CRF250", "status": "ready"},
            "car_brand": {"value": "HONDA", "status": "ready"},
            "include_road_tax": {"value": "false", "status": "ready"},
            "include_runner_fee": {"value": "false", "status": "ready"},
        },
        scalar_decisions={},
        warnings=[],
        status=RecordStatus.READY.value,
        display_options={"include_road_tax": False, "include_runner_fee": False},
    )
    session = Session(
        id="session-1",
        draft_id="draft-1",
        tenure_id="tenure-1",
        owner_id="staff-1",
        status="active",
        is_test=True,
    )
    session.draft = draft
    session.tenure = tenure
    db = FakeDb([draft, session, tenure, tv])
    user = SimpleNamespace(id="staff-1", role="staff")

    apply_workspace_patch(
        db,
        user,
        "draft-1",
        base_revision=3,
        operations=[
            {"op": "scalar_decision", "field": "car_model", "decision": "edit", "value": "HONDA CRF250"},
            {"op": "scalar_decision", "field": "include_road_tax", "decision": "edit", "value": "false"},
            {"op": "scalar_decision", "field": "include_runner_fee", "decision": "edit", "value": "false"},
        ],
    )

    assert tv.car_model == "HONDA CRF250"
    assert tenure.include_road_tax is False
    assert tenure.include_runner_fee is False

