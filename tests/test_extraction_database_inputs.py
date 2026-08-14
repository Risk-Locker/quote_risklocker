"""Extraction dictionaries are database inputs and remain request-local."""

from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.extraction.candidate_finder import find_candidates


def _values(candidates: dict, field: str) -> set[str]:
    return {candidate.value for candidate in candidates.get(field, [])}


def test_company_detection_uses_database_aliases_for_an_arbitrary_new_company():
    companies = [
        {
            "company_id": "company-nova",
            "name": "Nova Mutual",
            "source_template_category": "Other / Unknown",
            "aliases": ["nova motor", "nova-mutual"],
        }
    ]
    text = "Quotation issued by Nova Motor for TEST CUSTOMER"

    candidates = find_candidates(
        text,
        [{"page": 1, "text": text}],
        source_filename="2026_nova-mutual_quote.pdf",
        db_companies=companies,
    )

    assert _values(candidates, "insurance_company") == {"Nova Mutual"}
    assert any(candidate.source_method == "database_company_filename" for candidate in candidates["insurance_company"])


def test_no_company_is_invented_when_database_has_no_matching_alias():
    candidates = find_candidates(
        "QBE MOTOR QUOTATION",
        [{"page": 1, "text": "QBE MOTOR QUOTATION"}],
        source_filename="qbe.pdf",
        db_companies=[],
    )
    assert candidates.get("insurance_company", []) == []


def test_vehicle_dictionaries_do_not_leak_between_sequential_requests():
    text = "ORBIT ZEPHYR motor quotation"
    first = find_candidates(
        text,
        [{"page": 1, "text": text}],
        db_brands=["ORBIT"],
        db_models=["ZEPHYR"],
    )
    second = find_candidates(text, [{"page": 1, "text": text}])

    assert "ORBIT" in _values(first, "car_brand")
    assert "ZEPHYR" in _values(first, "car_model")
    assert "ORBIT" not in _values(second, "car_brand")
    assert "ZEPHYR" not in _values(second, "car_model")


def test_concurrent_requests_use_only_their_own_vehicle_dictionary():
    text = "ORBIT NOVA ZEPHYR COMET motor quotation"

    def extract(brand: str, model: str):
        return find_candidates(
            text,
            [{"page": 1, "text": text}],
            db_brands=[brand],
            db_models=[model],
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        orbit, nova = list(pool.map(lambda pair: extract(*pair), [("ORBIT", "ZEPHYR"), ("NOVA", "COMET")]))

    assert _values(orbit, "car_brand") == {"ORBIT"}
    assert _values(orbit, "car_model") == {"ZEPHYR"}
    assert _values(nova, "car_brand") == {"NOVA"}
    assert _values(nova, "car_model") == {"COMET"}
