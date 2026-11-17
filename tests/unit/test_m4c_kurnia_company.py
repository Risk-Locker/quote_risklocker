"""Hermetic TDD suite for Milestone 4c: Kurnia as a Separate Insurance Company."""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.config import get_settings
from app.db.init_db import seed_defaults
from app.extraction.company_resolution import build_companies_payload, resolve_company
from app.models.tables import Base, InsuranceCompany, new_id
from app.services.company_names import get_insurer_short_name, get_official_insurer_name


def test_kurnia_seed_is_idempotent_and_resolves_separately_from_amassurance():
    """P8: Kurnia seeds idempotently and resolves to Kurnia (never AmAssurance)."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    db: Session = factory()
    try:
        settings = get_settings()
        # Run seed_defaults twice to verify idempotency
        seed_defaults(db, settings)
        db.commit()
        seed_defaults(db, settings)
        db.commit()

        kurnia_rows = list(
            db.scalars(select(InsuranceCompany).where(InsuranceCompany.name == "Kurnia")).all()
        )
        assert len(kurnia_rows) == 1

        # Add AmAssurance alongside Kurnia and test company_resolution
        am_comp = InsuranceCompany(
            id=new_id(),
            slug="amassurance",
            name="AmAssurance",
            category="Motor",
            detection_phrases=["AmAssurance", "AmGeneral", "AmGeneral Insurance Berhad", "AmGen"],
            status="active",
        )
        db.add(am_comp)
        db.commit()

        all_companies = list(db.scalars(select(InsuranceCompany)).all())
        payload = build_companies_payload(all_companies)

        res_kurnia = resolve_company("Kurnia Insurans (Malaysia) Berhad", payload)
        assert res_kurnia["status"] == "matched"
        assert res_kurnia["display_name"] == "Kurnia"
        assert res_kurnia["company_id"] == kurnia_rows[0].id

        res_am = resolve_company("AmGeneral Insurance Berhad (AmAssurance)", payload)
        assert res_am["status"] == "matched"
        assert res_am["display_name"] == "AmAssurance"
        assert res_am["company_id"] == am_comp.id

        assert get_insurer_short_name("Kurnia Insurans (Malaysia) Berhad") == "Kurnia"
        assert get_official_insurer_name("KURNIA") == "Kurnia Insurans (Malaysia) Berhad"
        assert get_insurer_short_name("AmAssurance") == "AmAssurance"
    finally:
        db.close()
