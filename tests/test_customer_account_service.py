"""Hermetic unit tests for customer_account_service."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.tables import Base, CustomerAccount
from app.services.customer_account_service import (
    get_customer_account,
    list_customers,
    resolve_or_create_customer,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def test_resolve_or_create_new_company(db_session: Session):
    cust, disc = resolve_or_create_customer(
        db=db_session,
        raw_name="PL INKJET sdn bhd",
        raw_id="123456-X",
        phone="03-77889900",
        email="info@plinkjet.com.my",
        address="12, Jalan Ipoh, KL",
    )
    assert cust is not None
    assert cust.id_number == "123456X"
    assert cust.canonical_name == "PL INKJET SDN BHD"
    assert cust.entity_type == "corporate"
    assert cust.is_fleet is True
    assert "PL INKJET sdn bhd" in cust.name_aliases
    assert len(disc) == 0


def test_deduplicate_same_company_different_name_and_dot(db_session: Session):
    # Step 1: Ingest quote with "PL INKJET sdn bhd"
    cust1, disc1 = resolve_or_create_customer(
        db=db_session,
        raw_name="PL INKJET sdn bhd",
        raw_id="123456-X",
        phone="03-77889900",
    )
    db_session.commit()

    # Step 2: Later quote comes with "PL Inkjet SDN BHD." and same BRN
    cust2, disc2 = resolve_or_create_customer(
        db=db_session,
        raw_name="PL Inkjet SDN BHD.",
        raw_id="123456-X",
    )

    # Must resolve to the exact same customer!
    assert cust1.id == cust2.id
    assert cust2.canonical_name == "PL INKJET SDN BHD"
    # Both spellings are recorded in aliases
    assert "PL INKJET sdn bhd" in cust2.name_aliases
    assert "PL Inkjet SDN BHD." in cust2.name_aliases


def test_non_destructive_fill_of_empty_profile_fields(db_session: Session):
    # Step 1: Initial quote has name + BRN only (no email or address)
    cust1, _ = resolve_or_create_customer(
        db=db_session,
        raw_name="Megah Holdings Sdn Bhd",
        raw_id="202001012345",
        phone="012-3456789",
    )
    db_session.commit()
    assert cust1.email is None
    assert cust1.address is None

    # Step 2: Second quote for same BRN contains email and address
    cust2, disc = resolve_or_create_customer(
        db=db_session,
        raw_name="MEGAH HOLDINGS SDN BHD",
        raw_id="202001012345",
        phone="012-3456789",
        email="finance@megah.com",
        address="Tower 1, KLCC",
    )

    # Empty fields are safely enriched without asking!
    assert cust2.email == "finance@megah.com"
    assert cust2.address == "Tower 1, KLCC"
    assert len(disc) == 0


def test_discrepancy_alert_for_conflicting_phone(db_session: Session):
    # Customer registered with master phone
    cust1, _ = resolve_or_create_customer(
        db=db_session,
        raw_name="Tan Ah Kow",
        raw_id="850101-14-5555",
        phone="012-1111111",
    )
    db_session.commit()

    # New quote arrives with a different phone number
    cust2, disc = resolve_or_create_customer(
        db=db_session,
        raw_name="Tan Ah Kow",
        raw_id="850101-14-5555",
        phone="019-9999999",
    )

    # Master phone is NOT blind-overwritten!
    assert cust2.phone == "012-1111111"
    # New phone is preserved in alternate contacts
    alt_phones = [c["value"] for c in cust2.alternate_contacts if c["type"] == "phone"]
    assert "019-9999999" in alt_phones
    # Discrepancy alert is raised for staff review
    assert any(d["field"] == "phone" for d in disc)


def test_list_customers_search_and_fleet_filter(db_session: Session):
    resolve_or_create_customer(db_session, "PL INKJET sdn bhd", "123456-X")
    resolve_or_create_customer(db_session, "Ahmad bin Ali", "900101-10-1234")
    db_session.commit()

    # Search by name
    results, total = list_customers(db_session, search="inkjet")
    assert total == 1
    assert results[0].canonical_name == "PL INKJET SDN BHD"

    # Filter fleet only
    fleets, f_total = list_customers(db_session, is_fleet=True)
    assert f_total == 1
    assert fleets[0].canonical_name == "PL INKJET SDN BHD"
