import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sqlalchemy import select, delete

from app.db.session import SessionLocal
from app.models.tables import (
    BenefitCatalog,
    BenefitCatalogRevision,
    BenefitConcept,
    CatalogOffering,
    DraftBenefitSelection,
    InsuranceCompany,
    InsuranceProduct,
    QuotationDraft,
    User,
    new_id,
)
from app.services.business_setup_service import (
    retire_benefit_concept,
    restore_benefit_concept,
    get_catalog_workspace,
)
from app.services.catalog_review_service import seed_base_benefits
from app.rendering.render_context import resolve_benefit_cards


def test_retire_and_restore_benefit_concept_cascade():
    db = SessionLocal()
    try:
        admin_user = db.scalar(select(User).where(User.role == "admin"))
        if not admin_user:
            admin_user = User(
                id=new_id(),
                email="admin@test.local",
                role="admin",
                name="Admin",
                password_hash="mock",
            )
            db.add(admin_user)
            db.commit()

        # Create a test concept
        concept = BenefitConcept(
            id=new_id(),
            concept_key=f"test-cascade-{new_id()[:8]}",
            label="Test Cascade Benefit",
            status="active",
        )
        db.add(concept)

        company = db.scalar(select(InsuranceCompany))
        if not company:
            company = InsuranceCompany(id=new_id(), name="Test Insurer", company_key=f"test-ins-{new_id()[:6]}", status="active")
            db.add(company)
            db.commit()

        product = InsuranceProduct(
            id=new_id(),
            company_id=company.id,
            product_key=f"key-{new_id()[:6]}",
            name=f"Product-{new_id()[:6]}",
            status="active",
        )
        db.add(product)
        db.commit()

        # Create a draft revision and offering
        catalog = BenefitCatalog(
            id=new_id(),
            company_id=company.id,
            product_id=product.id,
            name="Test Catalog",
            status="active",
        )
        db.add(catalog)
        revision = BenefitCatalogRevision(
            id=new_id(),
            catalog_id=catalog.id,
            revision_number=1,
            state="draft",
            content_hash="mockhash123",
        )
        db.add(revision)

        offering = CatalogOffering(
            id=new_id(),
            catalog_revision_id=revision.id,
            offering_key=f"test-offering-{new_id()[:8]}",
            concept_id=concept.id,
            offering_kind="base",
            role="included",
            status="active",
        )
        db.add(offering)
        db.commit()

        # Retire the concept
        retire_benefit_concept(db, admin_user, concept.id)
        db.refresh(concept)
        db.refresh(offering)

        assert concept.status == "retired"
        assert offering.status == "retired"

        # Verify get_catalog_workspace excludes it
        workspace = get_catalog_workspace(db, admin_user, catalog.id)
        offering_ids = [o["id"] for o in workspace["offerings"]]
        assert offering.id not in offering_ids

        # Restore the concept
        restore_benefit_concept(db, admin_user, concept.id)
        db.refresh(concept)
        db.refresh(offering)

        assert concept.status == "active"
        assert offering.status == "active"

        # Workspace should now include it
        workspace_after = get_catalog_workspace(db, admin_user, catalog.id)
        offering_ids_after = [o["id"] for o in workspace_after["offerings"]]
        assert offering.id in offering_ids_after
    finally:
        try:
            if 'offering' in locals() and offering.id:
                db.execute(delete(CatalogOffering).where(CatalogOffering.id == offering.id))
            if 'concept' in locals() and concept.id:
                db.execute(delete(BenefitConcept).where(BenefitConcept.id == concept.id))
            db.commit()
        except Exception as e:
            import traceback
            traceback.print_exc()
            db.rollback()
        finally:
            db.close()


def test_seed_base_benefits_excludes_retired_concepts():
    db = SessionLocal()
    try:
        # Setup active concept & retired concept
        active_concept = BenefitConcept(
            id=new_id(),
            concept_key=f"test-active-{new_id()[:8]}",
            label="Active Seed Benefit",
            status="active",
        )
        retired_concept = BenefitConcept(
            id=new_id(),
            concept_key=f"test-retired-{new_id()[:8]}",
            label="Retired Seed Benefit",
            status="retired",
        )
        db.add_all([active_concept, retired_concept])

        company = db.scalar(select(InsuranceCompany))
        if not company:
            company = InsuranceCompany(id=new_id(), name="Test Insurer Seed", company_key=f"test-seed-{new_id()[:6]}", status="active")
            db.add(company)
            db.commit()

        product = InsuranceProduct(
            id=new_id(),
            company_id=company.id,
            product_key=f"seed-key-{new_id()[:6]}",
            name=f"Product-Seed-{new_id()[:6]}",
            status="active",
        )
        db.add(product)
        db.commit()

        catalog = BenefitCatalog(
            id=new_id(),
            company_id=company.id,
            product_id=product.id,
            name="Test Catalog Seed",
            status="active",
        )
        db.add(catalog)

        revision = BenefitCatalogRevision(
            id=new_id(),
            catalog_id=catalog.id,
            revision_number=1,
            state="draft",
            content_hash="pubhash123",
        )
        db.add(revision)

        active_offering = CatalogOffering(
            id=new_id(),
            catalog_revision_id=revision.id,
            offering_key=f"active-offering-{new_id()[:8]}",
            concept_id=active_concept.id,
            offering_kind="base",
            role="included",
            status="active",
        )
        retired_offering = CatalogOffering(
            id=new_id(),
            catalog_revision_id=revision.id,
            offering_key=f"retired-offering-{new_id()[:8]}",
            concept_id=retired_concept.id,
            offering_kind="base",
            role="included",
            status="active",  # Even if offering row is active in published catalog
        )
        db.add_all([active_offering, retired_offering])

        from app.models.tables import Batch, UploadedFile, User
        user = db.scalar(select(User))
        if not user:
            user = User(
                id=new_id(),
                email=f"test-{new_id()[:8]}@example.com",
                full_name="Test User",
                role="admin",
            )
            db.add(user)
            db.commit()

        batch = Batch(
            id=new_id(),
            owner_id=user.id,
            name="test-batch",
        )
        db.add(batch)
        db.commit()

        uploaded_file = UploadedFile(
            id=new_id(),
            batch_id=batch.id,
            owner_id=user.id,
            original_filename="test.pdf",
            content_type="application/pdf",
            storage_path="test.pdf",
        )
        db.add(uploaded_file)
        db.commit()

        draft = QuotationDraft(
            id=new_id(),
            uploaded_file_id=uploaded_file.id,
            owner_id=user.id,
            company_id=catalog.company_id,
            product_id=catalog.product_id,
            fields={},
        )
        db.add(draft)
        db.commit()

        # Seed base benefits
        count = seed_base_benefits(db, draft, revision)
        assert count >= 1
        db.flush()

        selections = db.scalars(
            select(DraftBenefitSelection).where(DraftBenefitSelection.draft_id == draft.id)
        ).all()
        concept_ids = [s.concept_id for s in selections]

        assert active_concept.id in concept_ids
        assert retired_concept.id not in concept_ids
    finally:
        try:
            if 'draft' in locals() and draft.id:
                db.execute(delete(DraftBenefitSelection).where(DraftBenefitSelection.draft_id == draft.id))
                db.execute(delete(QuotationDraft).where(QuotationDraft.id == draft.id))
            if 'uploaded_file' in locals() and uploaded_file.id:
                db.execute(delete(UploadedFile).where(UploadedFile.id == uploaded_file.id))
            if 'batch' in locals() and batch.id:
                db.execute(delete(Batch).where(Batch.id == batch.id))
            if 'active_offering' in locals() and active_offering.id:
                db.execute(delete(CatalogOffering).where(CatalogOffering.id == active_offering.id))
            if 'retired_offering' in locals() and retired_offering.id:
                db.execute(delete(CatalogOffering).where(CatalogOffering.id == retired_offering.id))
            if 'active_concept' in locals() and active_concept.id:
                db.execute(delete(BenefitConcept).where(BenefitConcept.id == active_concept.id))
            if 'retired_concept' in locals() and retired_concept.id:
                db.execute(delete(BenefitConcept).where(BenefitConcept.id == retired_concept.id))
            db.commit()
        except Exception as e:
            import traceback
            traceback.print_exc()
            db.rollback()
        finally:
            db.close()


def test_resolve_benefit_cards_excludes_retired_concepts():
    active_concept = SimpleNamespace(id="c-active", concept_key="active-key", label="Active", status="active", default_asset_id=None)
    retired_concept = SimpleNamespace(id="c-retired", concept_key="retired-key", label="Retired", status="retired", default_asset_id=None)

    active_sel = SimpleNamespace(
        id="s-1",
        draft_id="d-1",
        selection_key="catalog:active-offering",
        catalog_offering_id="off-1",
        concept_id="c-active",
        item_kind="catalog",
        state="current",
        sort_order=1,
        label_override=None,
        typed_value_override=None,
        price=None,
    )
    retired_sel = SimpleNamespace(
        id="s-2",
        draft_id="d-1",
        selection_key="catalog:retired-offering",
        catalog_offering_id="off-2",
        concept_id="c-retired",
        item_kind="catalog",
        state="current",
        sort_order=2,
        label_override=None,
        typed_value_override=None,
        price=None,
    )

    off_1 = SimpleNamespace(id="off-1", concept_id="c-active", status="active", sort_order=1, label_override=None, typed_value=None, offering_key="off-1", offering_kind="base", role="included", optional_price=None, presentation_facet_ids=[])
    off_2 = SimpleNamespace(id="off-2", concept_id="c-retired", status="active", sort_order=2, label_override=None, typed_value=None, offering_key="off-2", offering_kind="base", role="included", optional_price=None, presentation_facet_ids=[])

    resolved = resolve_benefit_cards(
        selections=[active_sel, retired_sel],
        offerings=[off_1, off_2],
        concepts=[active_concept, retired_concept],
        relations=[],
        facets=[],
    )

    current_concept_ids = [c["concept_id"] for c in resolved["current_benefits"]]
    assert "c-active" in current_concept_ids
    assert "c-retired" not in current_concept_ids
