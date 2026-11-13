"""Authoritative Malaysian Motor Insurance Towing Resolver.

Implements the official Malaysian Motor Insurance Towing Reference table
grounded in insurer PDS (Product Disclosure Sheets) and policy wording:
  - QBE: Standard RM500; Driver/Passenger Protector (N4) -> Unlimited
  - STMB / Takaful Malaysia: Standard 50km; Motor PA Plus P1=100km, P2=200km, P3=300km, P4=Unlimited
  - Etiqa: Standard 200km; OTO 360 -> Unlimited
  - Lonpac: Standard RM400; E-Assist Smart Driver P1=RM1,000, P2/EV=Unlimited
  - Berjaya Sompo: Standard/Rakan Auto=RM300; SOMPO Motor/MotorSafe=Unlimited
  - Tune Protect: Standard 200km; Motor Easy / AutoBuddy / Motor Shield -> Unlimited
  - AmAssurance (Amgen): auto365 Lite=RM200 (Breakdown Towing=150km), Plus=100km, Premier=365km
  - Kurnia: Standard RM200; Auto Assist Plus/Premier -> Unlimited

Constraint: Strictly outputs RM <amount>, <num>km, or Unlimited.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import re
from typing import Literal


@dataclass(frozen=True)
class TowingEntitlement:
    limit_type: Literal["RM", "km", "Unlimited"]
    formatted: str
    km_value: int | None = None
    rm_value: Decimal | None = None
    sort_weight: float = 0.0

    @classmethod
    def unlimited(cls) -> TowingEntitlement:
        return cls(limit_type="Unlimited", formatted="Unlimited", sort_weight=999_999.0)

    @classmethod
    def from_km(cls, km: int) -> TowingEntitlement:
        return cls(limit_type="km", formatted=f"{km} km", km_value=km, sort_weight=float(km))

    @classmethod
    def from_rm(cls, rm: int | Decimal) -> TowingEntitlement:
        dec = Decimal(str(rm))
        val_int = int(dec)
        fmt = f"RM {val_int:,}" if val_int >= 1000 else f"RM {val_int}"
        return cls(limit_type="RM", formatted=fmt, rm_value=dec, sort_weight=float(dec) * 0.5)


def resolve_towing_entitlement(
    company_name: str | None,
    product_name: str | None = None,
    package_or_rider: str | None = None,
    raw_document_text: str = "",
) -> TowingEntitlement:
    """Deterministically resolves towing limit into RM <amount>, <num> km, or Unlimited."""
    comp = (company_name or "").upper().strip()
    combined = " ".join([
        product_name or "",
        package_or_rider or "",
        raw_document_text or "",
    ]).lower()

    # 1. QBE
    if "QBE" in comp:
        if any(k in combined for k in ("passenger protector", "driver protector", "n4", "unlimited auto assistance")):
            return TowingEntitlement.unlimited()
        return TowingEntitlement.from_rm(500)

    # 2. STMB / Takaful Malaysia
    if "STMB" in comp or "TAKAFUL" in comp:
        # Check specific Motor PA Plus plans
        if "plan 4" in combined or "p4" in combined or "motor pa plus 4" in combined:
            return TowingEntitlement.unlimited()
        if "plan 3" in combined or "p3" in combined or "motor pa plus 3" in combined:
            return TowingEntitlement.from_km(300)
        if "plan 2" in combined or "p2" in combined or "motor pa plus 2" in combined:
            return TowingEntitlement.from_km(200)
        if "plan 1" in combined or "p1" in combined or "motor pa plus 1" in combined:
            return TowingEntitlement.from_km(100)
        if "unlimited" in combined or "tanpa had" in combined:
            return TowingEntitlement.unlimited()
        return TowingEntitlement.from_km(50)

    # 3. Etiqa
    if "ETIQA" in comp:
        if "oto 360" in combined or "oto360" in combined or "unlimited" in combined:
            return TowingEntitlement.unlimited()
        return TowingEntitlement.from_km(200)

    # 4. Lonpac
    if "LONPAC" in comp:
        if any(k in combined for k in ("plan 2", "ev plan", "smart driver 2", "smart driver - plan 2", "smart driver – plan 2")):
            return TowingEntitlement.unlimited()
        if any(k in combined for k in ("plan 1", "smart driver 1", "smart driver - plan 1", "smart driver – plan 1", "e-assist")):
            return TowingEntitlement.from_rm(1000)
        if "unlimited" in combined:
            return TowingEntitlement.unlimited()
        return TowingEntitlement.from_rm(400)

    # 5. Berjaya Sompo
    if "SOMPO" in comp or "BERJAYA" in comp:
        if any(k in combined for k in ("sompo motor", "motorsafe")):
            return TowingEntitlement.unlimited()
        if any(k in combined for k in ("rakan auto", "standard")):
            return TowingEntitlement.from_rm(300)
        if "unlimited" in combined:
            return TowingEntitlement.unlimited()
        return TowingEntitlement.from_rm(300)

    # 6. Tune Protect
    if "TUNE" in comp:
        if any(k in combined for k in ("motor easy", "autobuddy", "motor shield", "bundle")):
            return TowingEntitlement.unlimited()
        if "unlimited" in combined:
            return TowingEntitlement.unlimited()
        return TowingEntitlement.from_km(200)

    # 7. AmAssurance (Amgen)
    if "AMASSURANCE" in comp or "AMGEN" in comp or "AMGENERAL" in comp:
        if "lite" in combined:
            if "breakdown" in combined or "150" in combined:
                return TowingEntitlement.from_km(150)
            return TowingEntitlement.from_rm(200)
        if "plus" in combined or "100km" in combined:
            return TowingEntitlement.from_km(100)
        if "premier" in combined or "365km" in combined or "365 km" in combined or "365-km" in combined:
            return TowingEntitlement.from_km(365)
        if "unlimited" in combined:
            return TowingEntitlement.unlimited()
        # Default AmAssurance tier is auto365 Premier (365km)
        return TowingEntitlement.from_km(365)

    # 8. Kurnia
    if "KURNIA" in comp:
        if any(k in combined for k in ("plus", "premier", "auto assist plus", "auto assist premier", "unlimited")):
            return TowingEntitlement.unlimited()
        return TowingEntitlement.from_rm(200)

    # 9. Generic Fallback Parsing for unlisted insurers
    if any(k in combined for k in ("unlimited", "tanpa had", "24-hr unlimited")):
        return TowingEntitlement.unlimited()

    # Search for explicit KM pattern: e.g. "150 km", "200km"
    m_km = re.search(r"(\d+)\s*(?:km|kilomet(?:er|re)s?)\b", combined)
    if m_km:
        return TowingEntitlement.from_km(int(m_km.group(1)))

    # Search for explicit RM pattern: e.g. "RM 500", "RM1000"
    m_rm = re.search(r"rm\s*([\d,]+)", combined)
    if m_rm:
        clean_num = int(m_rm.group(1).replace(",", ""))
        return TowingEntitlement.from_rm(clean_num)

    return TowingEntitlement.unlimited()
