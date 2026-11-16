"""Pure domain double-entry accounting ledger engine for Malaysian motor insurance.

Enforces:
1. Exact Bank Negara Malaysia / GAAP double-entry ledger invariants:
   SUM(debit_amount) == SUM(credit_amount) > 0
2. Exact Python Decimal monetary math (zero IEEE-754 float drift).
3. Immutable append-only transaction design with reversing entry generation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP


TWO_PLACES = Decimal("0.01")


def to_decimal(amount: int | float | str | Decimal) -> Decimal:
    """Normalize monetary amount to Decimal(12, 2)."""
    if isinstance(amount, Decimal):
        return amount.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    return Decimal(str(amount)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


class UnbalancedJournalError(ValueError):
    """Raised when total debits do not equal total credits."""
    pass


class InvalidJournalAmountError(ValueError):
    """Raised when journal total is zero or negative."""
    pass


@dataclass(frozen=True)
class JournalLineDraft:
    account_code: str
    debit_amount: Decimal
    credit_amount: Decimal
    memo: str = ""
    sequence_order: int = 0

    def __post_init__(self):
        deb = to_decimal(self.debit_amount)
        crd = to_decimal(self.credit_amount)
        if deb < 0 or crd < 0:
            raise ValueError(f"Debit and Credit must be non-negative: debit={deb}, credit={crd}")
        if (deb > 0 and crd > 0) or (deb == 0 and crd == 0):
            raise ValueError(f"A journal line must have either a debit OR a credit, not both or neither: debit={deb}, credit={crd}")
        object.__setattr__(self, "debit_amount", deb)
        object.__setattr__(self, "credit_amount", crd)


@dataclass(frozen=True)
class JournalEntryDraft:
    entry_no: str
    entry_date: date
    description: str
    idempotency_key: str
    lines: list[JournalLineDraft]
    tenure_id: str | None = None
    invoice_id: str | None = None
    reverses_entry_id: str | None = None

    def __post_init__(self):
        if not self.lines:
            raise InvalidJournalAmountError("Journal entry must contain at least one line item.")
        total_debit = sum((line.debit_amount for line in self.lines), Decimal("0.00"))
        total_credit = sum((line.credit_amount for line in self.lines), Decimal("0.00"))

        if total_debit != total_credit:
            raise UnbalancedJournalError(
                f"Unbalanced journal entry '{self.entry_no}': total debit (RM {total_debit}) != total credit (RM {total_credit})"
            )
        if total_debit <= 0:
            raise InvalidJournalAmountError(f"Journal entry '{self.entry_no}' total amount must be > 0.00, got {total_debit}")


def build_invoice_issuance_journal(
    *,
    entry_no: str,
    entry_date: date,
    idempotency_key: str,
    tenure_id: str,
    invoice_id: str,
    vehicle_plate: str,
    gross_premium: Decimal | float | str,
    service_tax: Decimal | float | str,
    stamp_duty: Decimal | float | str,
    road_tax: Decimal | float | str = Decimal("0.00"),
    runner_fee: Decimal | float | str = Decimal("0.00"),
    discount: Decimal | float | str = Decimal("0.00"),
    commission_rate: Decimal | float | str = Decimal("0.10"),  # Default 10% motor commission
) -> JournalEntryDraft:
    """Build a balanced double-entry transaction when a motor quotation is won and invoice issued.

    Standard accounting postings:
      [DEBIT]  1200-AR-CLIENT       = Total Receivable from customer
      [DEBIT]  5010-ROAD-TAX-EXP    = Road tax outlay (if applicable)
      [CREDIT] 2100-AP-INSURER      = Net Motor Premium owed to Underwriter
      [CREDIT] 4010-COMM-REV        = Agency Commission earned
      [CREDIT] 4020-RUNNER-FEE      = Runner delivery fee earned
    """
    g_prem = to_decimal(gross_premium)
    s_tax = to_decimal(service_tax)
    s_duty = to_decimal(stamp_duty)
    r_tax = to_decimal(road_tax)
    r_fee = to_decimal(runner_fee)
    disc = to_decimal(discount)
    comm_pct = to_decimal(commission_rate)

    # 1. Total receivable from customer
    total_receivable = (g_prem + s_tax + s_duty + r_tax + r_fee - disc).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    # 2. Commission earned by agency on gross premium
    agency_commission = (g_prem * comm_pct).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    # 3. Net payable to insurer = (Gross Premium - Commission) + Service Tax + Stamp Duty
    insurer_payable = (g_prem - agency_commission + s_tax + s_duty).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    lines: list[JournalLineDraft] = []
    seq = 1

    # Debit Client Receivable
    lines.append(
        JournalLineDraft(
            account_code="1200-AR-CLIENT",
            debit_amount=total_receivable,
            credit_amount=Decimal("0.00"),
            memo=f"Motor Policy Invoice - {vehicle_plate}",
            sequence_order=seq,
        )
    )
    seq += 1

    # Credit Insurer Payable
    lines.append(
        JournalLineDraft(
            account_code="2100-AP-INSURER",
            debit_amount=Decimal("0.00"),
            credit_amount=insurer_payable,
            memo=f"Net Premium Payable - {vehicle_plate}",
            sequence_order=seq,
        )
    )
    seq += 1

    # Credit Agency Commission
    if agency_commission > Decimal("0.00"):
        lines.append(
            JournalLineDraft(
                account_code="4010-COMM-REV",
                debit_amount=Decimal("0.00"),
                credit_amount=agency_commission,
                memo=f"Agency Commission ({comm_pct * 100:.0f}%) - {vehicle_plate}",
                sequence_order=seq,
            )
        )
        seq += 1

    # Credit Runner Fee
    if r_fee > Decimal("0.00"):
        lines.append(
            JournalLineDraft(
                account_code="4020-RUNNER-FEE",
                debit_amount=Decimal("0.00"),
                credit_amount=r_fee,
                memo=f"Runner JPJ Delivery Fee - {vehicle_plate}",
                sequence_order=seq,
            )
        )
        seq += 1

    # Credit Road Tax Pass-through (Disbursed directly or held)
    if r_tax > Decimal("0.00"):
        # If road tax was added to client receivable, credit offset is road tax liability/payable
        lines.append(
            JournalLineDraft(
                account_code="5010-ROAD-TAX-EXP",
                debit_amount=Decimal("0.00"),
                credit_amount=r_tax,
                memo=f"Road Tax Collection - {vehicle_plate}",
                sequence_order=seq,
            )
        )
        seq += 1

    # Debit Discount (Contra-Revenue deduction if provided)
    if disc > Decimal("0.00"):
        lines.append(
            JournalLineDraft(
                account_code="4010-COMM-REV",
                debit_amount=disc,
                credit_amount=Decimal("0.00"),
                memo=f"Courtesy Discount - {vehicle_plate}",
                sequence_order=seq,
            )
        )
        seq += 1

    return JournalEntryDraft(
        entry_no=entry_no,
        entry_date=entry_date,
        description=f"Motor Policy Invoicing for {vehicle_plate}",
        idempotency_key=idempotency_key,
        lines=lines,
        tenure_id=tenure_id,
        invoice_id=invoice_id,
    )


def build_client_payment_journal(
    *,
    entry_no: str,
    entry_date: date,
    idempotency_key: str,
    tenure_id: str,
    invoice_id: str,
    vehicle_plate: str,
    amount_paid: Decimal | float | str,
    payment_reference: str = "",
) -> JournalEntryDraft:
    """Record client payment received into the agency operating bank account.

    Postings:
      [DEBIT]  1010-BANK-HLB     = Cash received into bank
      [CREDIT] 1200-AR-CLIENT     = Reduce client receivable
    """
    amt = to_decimal(amount_paid)
    ref_suffix = f" (Ref: {payment_reference})" if payment_reference else ""

    lines = [
        JournalLineDraft(
            account_code="1010-BANK-HLB",
            debit_amount=amt,
            credit_amount=Decimal("0.00"),
            memo=f"Payment received for {vehicle_plate}{ref_suffix}",
            sequence_order=1,
        ),
        JournalLineDraft(
            account_code="1200-AR-CLIENT",
            debit_amount=Decimal("0.00"),
            credit_amount=amt,
            memo=f"Client receivable clearance for {vehicle_plate}",
            sequence_order=2,
        ),
    ]

    return JournalEntryDraft(
        entry_no=entry_no,
        entry_date=entry_date,
        description=f"Client Collection for {vehicle_plate}",
        idempotency_key=idempotency_key,
        lines=lines,
        tenure_id=tenure_id,
        invoice_id=invoice_id,
    )


def build_insurer_settlement_journal(
    *,
    entry_no: str,
    entry_date: date,
    idempotency_key: str,
    tenure_id: str,
    insurer_name: str,
    vehicle_plate: str,
    amount_settled: Decimal | float | str,
    settlement_reference: str = "",
) -> JournalEntryDraft:
    """Record remittance payout from agency bank account to insurer.

    Postings:
      [DEBIT]  2100-AP-INSURER   = Reduce underwriter payable
      [CREDIT] 1010-BANK-HLB     = Cash disbursed from bank
    """
    amt = to_decimal(amount_settled)
    ref_suffix = f" (Ref: {settlement_reference})" if settlement_reference else ""

    lines = [
        JournalLineDraft(
            account_code="2100-AP-INSURER",
            debit_amount=amt,
            credit_amount=Decimal("0.00"),
            memo=f"Remittance to {insurer_name} for {vehicle_plate}{ref_suffix}",
            sequence_order=1,
        ),
        JournalLineDraft(
            account_code="1010-BANK-HLB",
            debit_amount=Decimal("0.00"),
            credit_amount=amt,
            memo=f"Bank payout to {insurer_name} for {vehicle_plate}",
            sequence_order=2,
        ),
    ]

    return JournalEntryDraft(
        entry_no=entry_no,
        entry_date=entry_date,
        description=f"Insurer Settlement Payout to {insurer_name} ({vehicle_plate})",
        idempotency_key=idempotency_key,
        lines=lines,
        tenure_id=tenure_id,
    )


def build_reversing_journal(
    original_entry: JournalEntryDraft,
    *,
    reversal_entry_no: str,
    reversal_date: date,
    reversal_idempotency_key: str,
    reason: str,
) -> JournalEntryDraft:
    """Construct an exact mirror reversing journal entry (swapping debits and credits)."""
    reversing_lines: list[JournalLineDraft] = []
    for line in original_entry.lines:
        reversing_lines.append(
            JournalLineDraft(
                account_code=line.account_code,
                debit_amount=line.credit_amount,
                credit_amount=line.debit_amount,
                memo=f"REVERSAL: {line.memo} (Reason: {reason})",
                sequence_order=line.sequence_order,
            )
        )

    return JournalEntryDraft(
        entry_no=reversal_entry_no,
        entry_date=reversal_date,
        description=f"REVERSAL of {original_entry.entry_no}: {reason}",
        idempotency_key=reversal_idempotency_key,
        lines=reversing_lines,
        tenure_id=original_entry.tenure_id,
        invoice_id=original_entry.invoice_id,
        reverses_entry_id=original_entry.entry_no,
    )
