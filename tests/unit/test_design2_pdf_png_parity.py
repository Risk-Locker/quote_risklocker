"""Regression tests for Design 2 PDF/PNG visual, logo, footer, and total parity."""

from __future__ import annotations

import base64
from io import BytesIO
import sys
from unittest.mock import patch

from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.tables import (
    Base,
    BenefitCatalog,
    BenefitCatalogRevision,
    DraftBenefitSelection,
    InsuranceCompany,
    InsuranceProduct,
    OutputTemplateConfig,
    QuotationDraft,
    TemplatePageProfile,
    TemplateRevision,
    UploadedFile,
    User,
    Batch,
)
from app.rendering.benefit_schedule_renderer import (
    _trim_image_padding_data_uri,
    get_company_logo_data_uri,
    get_design2_asset_uris,
    render_design2_footer_html,
)
from app.rendering.template_renderer_design2 import render_design2_html
from app.services.generation_service import build_render_snapshot_context
from app.services.master_template_service import motor_modern_design_2_config


def _decode_png_size(data_uri: str) -> tuple[int, int]:
    _, b64 = data_uri.split(",", 1)
    with Image.open(BytesIO(base64.b64decode(b64))) as im:
        return im.size


def test_trim_image_padding_works_without_numpy():
    img = Image.new("RGBA", (600, 600), (0, 0, 0, 0))
    for y in range(250, 330):
        for x in range(80, 520):
            img.putpixel((x, y), (229, 35, 32, 255))
    buf = BytesIO()
    img.save(buf, format="PNG")
    raw_uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")

    with patch.dict(sys.modules, {"numpy": None}):
        trimmed_uri = _trim_image_padding_data_uri(raw_uri)

    w, h = _decode_png_size(trimmed_uri)
    assert w > h * 3
    assert 435 <= w <= 450
    assert 75 <= h <= 90


def test_design2_assets_resolve_wide_horizontal_logos_without_numpy():
    with patch.dict(sys.modules, {"numpy": None}):
        assets = get_design2_asset_uris("AmAssurance")
        amgen_uri = get_company_logo_data_uri("AmAssurance")

    assert assets["rl_logo_uri"].startswith("data:image/")
    rl_w, rl_h = _decode_png_size(assets["rl_logo_uri"])
    assert rl_w > rl_h * 3, f"Expected wide horizontal RL logo, got {(rl_w, rl_h)}"

    assert amgen_uri.startswith("data:image/")
    am_w, am_h = _decode_png_size(amgen_uri)
    assert am_w > am_h * 1.5, f"Expected horizontal AmAssurance banner, got {(am_w, am_h)}"


def test_design2_footer_and_html_enforce_capital_company_and_full_reg_no():
    footer = render_design2_footer_html("data:image/png;base64,AA==")
    assert "RISKLOCKER SDN. BHD." in footer
    assert "202301041962(1535879-U)" in footer

    html = render_design2_html(
        draft_fields={
            "customer_name": "M. A. TRANSPORTATION SDN BHD",
            "vehicle_no": "VRS7732",
            "insurance_company": "AMASSURANCE",
            "premium": "13,004.20",
            "roadtax": "127,510.00",
            "runner_fee": "20.00",
            "total_amount": "13,004.20",
            "total_premium_adjusted": "140,534.00",
        }
    )
    assert "RISKLOCKER SDN. BHD." in html
    assert "202301041962(1535879-U)" in html
    assert "RM 140,534.00" in html


def test_snapshot_context_uses_adjusted_total_unless_manual_override_and_respects_disabled_fees():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        from app.models.tables import new_id

        uid, cid, pid, catid, crevid = new_id(), new_id(), new_id(), new_id(), new_id()
        tid, pgid, trevid, bid, fid, did = new_id(), new_id(), new_id(), new_id(), new_id(), new_id()
        user = User(id=uid, email="admin@test.com", name="Admin", role="super_admin", password_hash="x")
        comp = InsuranceCompany(id=cid, name="AmAssurance", slug="amassurance", detection_phrases=[], status="active")
        prod = InsuranceProduct(id=pid, company_id=cid, product_key="comm-lorry", name="Commercial Lorry", status="active")
        cat = BenefitCatalog(id=catid, company_id=cid, product_id=pid, name="Commercial", status="active")
        cat_rev = BenefitCatalogRevision(id=crevid, catalog_id=catid, revision_number=1, state="published", content_hash="ch1")
        tmpl = OutputTemplateConfig(id=tid, insurance_company_id=None, name="Design 2", status="active")
        page = TemplatePageProfile(id=pgid, profile_key="a4", name="A4", width=794, height=1123, unit="px", safe_margins={}, bleed={})
        t_rev = TemplateRevision(
            id=trevid,
            template_id=tid,
            page_profile_id=pgid,
            revision_number=1,
            state="published",
            config=motor_modern_design_2_config(),
            config_hash="h1",
        )
        batch = Batch(id=bid, owner_id=uid, name="Batch 1", status="ready")
        up = UploadedFile(
            id=fid,
            batch_id=bid,
            owner_id=uid,
            original_filename="quote.pdf",
            content_type="application/pdf",
            size_bytes=1234,
            storage_provider="local_ephemeral",
            storage_path="quote.pdf",
            storage_sha256="abc",
            status="ready",
        )
        draft = QuotationDraft(
            id=did,
            uploaded_file_id=fid,
            owner_id=uid,
            company_id=cid,
            product_id=pid,
            catalog_revision_id=crevid,
            template_revision_id=trevid,
            revision=2,
            status="ready",
            fields={
                "customer_name": {"value": "M. A. TRANSPORTATION SDN BHD"},
                "vehicle_no": {"value": "VRS7732"},
                "insurance_company": {"value": "AMASSURANCE"},
                "premium": {"value": "13,004.20"},
                "roadtax": {"value": "127,510.00"},
                "service_fee": {"value": "20.00"},
                "total_amount": {"value": "13,004.20"},
            },
            scalar_decisions={"total_amount": {"decision": "confirm"}},
            display_options={"round_total": True, "include_road_tax": True, "include_runner_fee": True},
        )
        db.add_all([user, comp, prod, cat, cat_rev, tmpl, page, t_rev, batch, up, draft])
        db.flush()

        ctx_included, _ = build_render_snapshot_context(db, draft, t_rev)
        assert ctx_included["fields"]["total_premium_adjusted"]["value"] == "140,534.00"
        assert ctx_included["fields"]["total_amount"]["value"] == "140,534.00"

        draft.display_options = {"round_total": True, "include_road_tax": False, "include_runner_fee": False}
        db.flush()
        ctx_disabled, _ = build_render_snapshot_context(db, draft, t_rev)
        assert ctx_disabled["fields"]["roadtax"]["value"] == "0.00"
        assert ctx_disabled["fields"]["service_fee"]["value"] == "0.00"
        assert ctx_disabled["fields"]["total_amount"]["value"] == "13,004.00"

        draft.display_options = {"round_total": True, "include_road_tax": True, "include_runner_fee": True}
        draft.fields["total_amount"] = {"value": "99,999.00"}
        draft.scalar_decisions = {"total_amount": {"decision": "edit"}}
        db.flush()
        ctx_manual, _ = build_render_snapshot_context(db, draft, t_rev)
        assert ctx_manual["fields"]["total_amount"]["value"] == "99,999.00"
