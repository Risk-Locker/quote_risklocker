"""Unit tests for the double-entry accounting ledger domain engine and ORM models."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.domain.ledger.ledger_engine import (
    JournalEntryDraft,
    JournalLineDraft,
    UnbalancedJournalError,
    InvalidJournalAmountError,
    build_invoice_issuance_journal,
    build_client_payment_journal,
    build_insurer_settlement_journal,
    build_reversing_journal,
    to_decimal,
)
from app.models.tables import Base, LedgerAccount, LedgerInvoice, JournalEntry, JournalLine, InsuranceTenure, CustomerAccount, TrackedVehicle, User


def test_to_decimal_quantization():
    assert to_decimal(100) == Decimal("100.00")
    assert to_decimal("25.5") == Decimal("25.50")
    assert to_decimal(14.994) == Decimal("14.99")
    assert to_decimal(14.995) == Decimal("15.00")


def test_journal_line_validation():
    # Valid line
    line = JournalLineDraft(account_code="1010-BANK-HLB", debit_amount=Decimal("150.00"), credit_amount=Decimal("0.00"))
    assert line.debit_amount == Decimal("150.00")
    assert line.credit_amount == Decimal("0.00")

    # Negative amount rejected
    with pytest.raises(ValueError, match="Debit and Credit must be non-negative"):
        JournalLineDraft(account_code="1010-BANK-HLB", debit_amount=Decimal("-10.00"), credit_amount=Decimal("0.00"))

    # Both debit and credit non-zero rejected
    with pytest.raises(ValueError, match="either a debit OR a credit, not both"):
        JournalLineDraft(account_code="1010-BANK-HLB", debit_amount=Decimal("10.00"), credit_amount=Decimal("10.00"))

    # Both debit and credit zero rejected
    with pytest.raises(ValueError, match="either a debit OR a credit, not both"):
        JournalLineDraft(account_code="1010-BANK-HLB", debit_amount=Decimal("0.00"), credit_amount=Decimal("0.00"))


def test_unbalanced_journal_rejected():
    lines = [
        JournalLineDraft(account_code="1010-BANK-HLB", debit_amount=Decimal("100.00"), credit_amount=Decimal("0.00")),
        JournalLineDraft(account_code="1200-AR-CLIENT", debit_amount=Decimal("0.00"), credit_amount=Decimal("99.99")),
    ]
    with pytest.raises(UnbalancedJournalError, match="Unbalanced journal entry"):
        JournalEntryDraft(
            entry_no="JE-2026-001",
            entry_date=date.today(),
            description="Test",
            idempotency_key="key-1",
            lines=lines,
        )


def test_build_invoice_issuance_journal_perfectly_balanced():
    # Gross: 1000.00, Tax: 80.00 (8%), Stamp: 10.00, RoadTax: 90.00, Runner: 25.00, Disc: 15.00, Comm: 10%
    je = build_invoice_issuance_journal(
        entry_no="JE-INV-001",
        entry_date=date(2026, 11, 14),
        idempotency_key="idemp-inv-001",
        tenure_id="tenure-123",
        invoice_id="inv-123",
        vehicle_plate="WXY1234",
        gross_premium=Decimal("1000.00"),
        service_tax=Decimal("80.00"),
        stamp_duty=Decimal("10.00"),
        road_tax=Decimal("90.00"),
        runner_fee=Decimal("25.00"),
        discount=Decimal("15.00"),
        commission_rate=Decimal("0.10"),
    )

    total_debits = sum(line.debit_amount for line in je.lines)
    total_credits = sum(line.credit_amount for line in je.lines)

    # Total Receivable = 1000 + 80 + 10 + 90 + 25 - 15 = 1190.00
    # Contra discount = 15.00
    # Total debits = 1190 + 15 = 1205.00
    # Insurer Payable = 900 + 80 + 10 = 990.00
    # Commission = 100.00
    # Runner fee = 25.00
    # Road tax = 90.00
    # Total credits = 990 + 100 + 25 + 90 = 1205.00
    assert total_debits == total_credits
    assert total_debits == Decimal("1205.00")
    assert je.tenure_id == "tenure-123"
    assert je.invoice_id == "inv-123"


def test_build_client_payment_and_insurer_settlement():
    pay_je = build_client_payment_journal(
        entry_no="JE-PAY-001",
        entry_date=date(2026, 11, 14),
        idempotency_key="idemp-pay-001",
        tenure_id="tenure-123",
        invoice_id="inv-123",
        vehicle_plate="WXY1234",
        amount_paid=Decimal("1190.00"),
        payment_reference="HLB-TXN-88219",
    )
    assert sum(l.debit_amount for l in pay_je.lines) == sum(l.credit_amount for l in pay_je.lines) == Decimal("1190.00")

    settle_je = build_insurer_settlement_journal(
        entry_no="JE-SET-001",
        entry_date=date(2026, 11, 15),
        idempotency_key="idemp-set-001",
        tenure_id="tenure-123",
        insurer_name="Etiqa",
        vehicle_plate="WXY1234",
        amount_settled=Decimal("990.00"),
        settlement_reference="ETIQA-REMIT-901",
    )
    assert sum(l.debit_amount for l in settle_je.lines) == sum(l.credit_amount for l in settle_je.lines) == Decimal("990.00")


def test_build_reversing_journal():
    orig_je = build_client_payment_journal(
        entry_no="JE-PAY-002",
        entry_date=date(2026, 11, 14),
        idempotency_key="idemp-pay-002",
        tenure_id="tenure-123",
        invoice_id="inv-123",
        vehicle_plate="WXY1234",
        amount_paid=Decimal("500.00"),
    )
    rev_je = build_reversing_journal(
        orig_je,
        reversal_entry_no="JE-REV-002",
        reversal_date=date(2026, 11, 16),
        reversal_idempotency_key="idemp-rev-002",
        reason="Cheque bounced",
    )
    assert rev_je.reverses_entry_id == "JE-PAY-002"
    assert sum(l.debit_amount for l in rev_je.lines) == sum(l.credit_amount for l in rev_je.lines) == Decimal("500.00")

    # Original debit was 1010-BANK-HLB; reversal debit must be 1200-AR-CLIENT
    assert rev_je.lines[0].account_code == "1010-BANK-HLB"
    assert rev_je.lines[0].credit_amount == Decimal("500.00")
    assert rev_je.lines[1].account_code == "1200-AR-CLIENT"
    assert rev_je.lines[1].debit_amount == Decimal("500.00")


def test_sqlite_in_memory_orm_persistence():
    """Verify SQLAlchemy ORM models work hermetically in SQLite."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    with session_factory() as db:
        # 1. Create accounts
        bank_acc = LedgerAccount(code="1010-BANK-HLB", name="Bank", account_type="asset", normal_side="debit")
        ar_acc = LedgerAccount(code="1200-AR-CLIENT", name="AR", account_type="asset", normal_side="debit")
        db.add_all([bank_acc, ar_acc])
        db.flush()

        # 2. Create customer, vehicle, tenure
        cust = CustomerAccount(canonical_name="Test Customer", id_number="900101-14-1234")
        veh = TrackedVehicle(vehicle_no="ABC1234", is_provisional=False)
        db.add_all([cust, veh])
        db.flush()

        tenure = InsuranceTenure(
            customer_id=cust.id,
            tracked_vehicle_id=veh.id,
            vehicle_no=veh.vehicle_no,
            customer_name=cust.canonical_name,
            coverage_start_date=date(2026, 1, 1),
            coverage_end_date=date(2026, 12, 31),
            expiry_month="12",
        )
        db.add(tenure)
        db.flush()

        # 3. Create invoice
        invoice = LedgerInvoice(
            tenure_id=tenure.id,
            invoice_no="INV-2026-TEST",
            gross_premium=Decimal("800.00"),
            total_receivable=Decimal("800.00"),
        )
        db.add(invoice)
        db.flush()

        # 4. Create journal entry and lines
        je = JournalEntry(
            entry_no="JE-2026-TEST",
            entry_date=date.today(),
            description="Test entry",
            idempotency_key="idemp-test-orm",
            tenure_id=tenure.id,
            invoice_id=invoice.id,
        )
        db.add(je)
        db.flush()

        l1 = JournalLine(journal_entry_id=je.id, account_id=bank_acc.id, debit_amount=Decimal("800.00"), credit_amount=Decimal("0.00"), sequence_order=1)
        l2 = JournalLine(journal_entry_id=je.id, account_id=ar_acc.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("800.00"), sequence_order=2)
        db.add_all([l1, l2])
        db.commit()

        # Query back and verify relations
        saved_je = db.query(JournalEntry).filter_by(entry_no="JE-2026-TEST").first()
        assert saved_je is not None
        assert len(saved_je.lines) == 2
        assert saved_je.lines[0].debit_amount == Decimal("800.00")
        assert saved_je.lines[1].credit_amount == Decimal("800.00")
        assert saved_je.invoice.invoice_no == "INV-2026-TEST"
