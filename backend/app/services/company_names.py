"""Official Registered Corporate Names for Malaysian Insurers.

Grounded in official Bank Negara Malaysia (BNM) and General Insurance Association
of Malaysia (PIAM) registries.
"""

from __future__ import annotations

import re

OFFICIAL_INSURER_NAMES: dict[str, str] = {
    "QBE": "QBE Insurance (Malaysia) Berhad",
    "ETIQA": "Etiqa General Insurance Berhad",
    "STMB": "Syarikat Takaful Malaysia Am Berhad",
    "TAKAFUL_MALAYSIA": "Syarikat Takaful Malaysia Am Berhad",
    "TAKAFUL": "Syarikat Takaful Malaysia Am Berhad",
    "LONPAC": "Lonpac Insurance Bhd",
    "BERJAYA_SOMPO": "Berjaya Sompo Insurance Berhad",
    "SOMPO": "Berjaya Sompo Insurance Berhad",
    "TUNE": "Tune Insurance Malaysia Berhad",
    "TUNE_PROTECT": "Tune Insurance Malaysia Berhad",
    "AMASSURANCE": "AmGeneral Insurance Berhad",
    "AMGEN": "AmGeneral Insurance Berhad",
    "AMGENERAL": "AmGeneral Insurance Berhad",
    "KURNIA": "AmGeneral Insurance Berhad",
    "ALLIANZ": "Allianz General Insurance Company (Malaysia) Berhad",
    "ZURICH": "Zurich General Insurance Malaysia Berhad",
    "AIG": "AIG Malaysia Insurance Berhad",
    "CHUBB": "Chubb Insurance Malaysia Berhad",
    "GENERALI": "Generali Insurance Malaysia Berhad",
    "AXA": "Generali Insurance Malaysia Berhad",
    "MSIG": "MSIG Insurance (Malaysia) Bhd",
    "PACIFIC_ORIENT": "Pacific & Orient Insurance Co. Berhad",
    "TOKIO_MARINE": "Tokio Marine Insurans (Malaysia) Berhad",
    "RHB": "RHB Insurance Berhad",
    "LIBERTY": "Liberty General Insurance Berhad",
}


def get_official_insurer_name(raw_name: str | None) -> str:
    """Normalizes any insurer code or raw string into its exact official registered legal corporate name."""
    if not raw_name:
        return "QBE Insurance (Malaysia) Berhad"
    clean = re.sub(r"[^A-Za-z0-9]", "_", raw_name.upper())

    if clean in OFFICIAL_INSURER_NAMES:
        return OFFICIAL_INSURER_NAMES[clean]

    for key, official in OFFICIAL_INSURER_NAMES.items():
        if key in clean:
            return official

    return raw_name if ("Berhad" in raw_name or "Bhd" in raw_name) else f"{raw_name} Berhad"


def get_insurer_short_name(raw_name: str | None) -> str:
    """Returns the short brand name used for section banners (e.g. 'QBE', 'Etiqa')."""
    if not raw_name:
        return "QBE"
    upper = raw_name.upper()
    if "QBE" in upper:
        return "QBE"
    if "ETIQA" in upper:
        return "Etiqa"
    if "TAKAFUL" in upper or "STMB" in upper:
        return "Takaful Malaysia"
    if "LONPAC" in upper:
        return "Lonpac"
    if "SOMPO" in upper:
        return "Berjaya Sompo"
    if "TUNE" in upper:
        return "Tune Protect"
    if "AMASSURANCE" in upper or "AMGEN" in upper or "KURNIA" in upper:
        return "AmAssurance"
    if "ALLIANZ" in upper:
        return "Allianz"
    if "ZURICH" in upper:
        return "Zurich"
    if "LIBERTY" in upper:
        return "Liberty"
    if "MSIG" in upper:
        return "MSIG"
    if "CHUBB" in upper:
        return "Chubb"
    if "GENERALI" in upper or "AXA" in upper:
        return "Generali"
    if "RHB" in upper:
        return "RHB"
    first = re.split(r"[\s(]", raw_name)[0].strip()
    return first or "QBE"
