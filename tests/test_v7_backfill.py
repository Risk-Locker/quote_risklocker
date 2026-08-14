"""Deterministic, non-destructive v7 compatibility backfill planning."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import json

import pytest

from app.services.v7_backfill import apply_backfill_plan, build_backfill_plan, report_path


def company(company_id: str, name: str, aliases: list[str]):
    return SimpleNamespace(id=company_id, name=name, detection_phrases=aliases)


def special(special_id: str, label: str, variants: list[object]):
    return SimpleNamespace(id=special_id, label=label, category="FOC", variants=variants)


def variant(variant_id: str, label: str, value_text: str | None = None):
    return SimpleNamespace(id=variant_id, label=label, value_text=value_text, icon_asset_id=None)


def template(template_id: str, name: str, company_id: str | None = None):
    return SimpleNamespace(
        id=template_id,
        name=name,
        insurance_company_id=company_id,
        fixed_fields={"canvas": {"width": 794, "height": 1123, "elements": []}},
    )


def test_backfill_plan_is_deterministic_and_never_deletes_or_guesses_special_company():
    inputs = {
        "companies": [company("c1", "QBE", ["QBE Insurance", "qbe"])],
        "specials": [special("s1", "Towing", [variant("v1", "Unlimited Towing", "Unlimited")])],
        "templates": [template("t1", "Legacy QBE", "c1")],
    }

    first = build_backfill_plan(**inputs)
    second = build_backfill_plan(**inputs)

    assert first == second
    assert first["schema_version"] == 1
    assert all(action["operation"] in {"upsert", "preserve"} for action in first["actions"])
    assert not any(action.get("company_id") for action in first["actions"] if action["entity"] in {"compatibility_catalog", "compatibility_offering"})
    assert any(action["entity"] == "company_alias" and action["company_id"] == "c1" for action in first["actions"])
    assert any(action["entity"] == "compatibility_template_revision" and action["legacy_company_id"] == "c1" for action in first["actions"])
    assert first["summary"]["delete_count"] == 0
    assert first["summary"]["guessed_company_count"] == 0


def test_backfill_plan_reports_alias_and_variant_collisions_without_silent_merge():
    plan = build_backfill_plan(
        companies=[
            company("c1", "Alpha", ["Shared Alias"]),
            company("c2", "Beta", ["shared   alias"]),
        ],
        specials=[
            special("s1", "Towing", [variant("v1", "Unlimited"), variant("v2", " unlimited ")]),
        ],
        templates=[],
    )

    kinds = {warning["kind"] for warning in plan["warnings"]}
    assert "duplicate_company_alias" in kinds
    assert "duplicate_legacy_variant_label" in kinds
    alias_actions = [action for action in plan["actions"] if action["entity"] == "company_alias"]
    assert {action["normalized_alias"] for action in alias_actions} == {"alpha", "beta"}
    assert all(action["normalized_alias"] != "shared alias" for action in alias_actions)


def test_backfill_plan_preserves_legacy_version_and_draft_counts_without_rewrite():
    plan = build_backfill_plan(
        companies=[],
        specials=[],
        templates=[],
        legacy_draft_ids=["d1", "d2"],
        legacy_version_ids=["g1"],
    )

    preserve = [action for action in plan["actions"] if action["operation"] == "preserve"]
    assert {(item["entity"], item["legacy_id"]) for item in preserve} == {
        ("legacy_draft", "d1"),
        ("legacy_draft", "d2"),
        ("generated_version", "g1"),
    }
    assert plan["summary"]["legacy_drafts_preserved"] == 2
    assert plan["summary"]["generated_versions_preserved"] == 1


class Result:
    rowcount = 1


class CaptureDb:
    def __init__(self):
        self.calls = []
        self.commits = 0

    def execute(self, statement, params=None):
        self.calls.append((str(statement), params or {}))
        return Result()

    def commit(self):
        self.commits += 1

    def rollback(self):
        raise AssertionError("The valid compatibility plan must not roll back.")


def test_apply_uses_only_idempotent_inserts_and_ignores_preserve_actions():
    plan = build_backfill_plan(
        companies=[company("c1", "QBE", ["QBE Insurance"])],
        specials=[special("s1", "Towing", [variant("v1", "Unlimited", "Unlimited")])],
        templates=[template("t1", "Legacy", "c1")],
        legacy_draft_ids=["d1"],
        legacy_version_ids=["g1"],
    )
    db = CaptureDb()

    result = apply_backfill_plan(db, plan)

    assert result["statements"] == len(db.calls)
    assert result["inserted_or_present"] == len(db.calls)
    assert db.commits == 1
    assert db.calls
    for sql, _params in db.calls:
        normalized = " ".join(sql.upper().split())
        assert normalized.startswith("INSERT INTO")
        assert "ON CONFLICT DO NOTHING" in normalized
        assert " DELETE " not in f" {normalized} "
        assert " UPDATE " not in f" {normalized} "


def test_report_path_must_stay_inside_repository_qc_tmp(tmp_path: Path):
    workspace = tmp_path / "repo"
    safe = report_path(workspace, Path(".qc-tmp/backfill-report.json"))
    assert safe == (workspace / ".qc-tmp" / "backfill-report.json").resolve()

    with pytest.raises(ValueError, match=".qc-tmp"):
        report_path(workspace, Path("report.json"))
    with pytest.raises(ValueError, match=".qc-tmp"):
        report_path(workspace, Path(".qc-tmp/../../outside.json"))
