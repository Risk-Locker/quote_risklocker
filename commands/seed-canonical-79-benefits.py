"""Seed all 79 canonical benefits into benefit_concepts and configure company benefit pools.

Phase 1:
- Upsert 79 canonical benefits into benefit_concepts from docs/benefits/concise/all_benefits.md
- Newly created benefits get default_asset_id = None (artwork to be added later by user)
- Calibrated descriptions (<80 chars) populated as baseline concept descriptions
- Populate benefit_aliases with known aliases from all_benefits.md

Phase 2:
- Parse docs/benefits/concise/company_all_benefits-v4.md
- Upsert company_benefit_configs for all 7 insurers:
    Lonpac Insurance (48)
    Etiqa Insurance & Takaful (42)
    Tune Protect Insurance (40)
    AmAssurance / Liberty (37)
    QBE Insurance (37)
    STMB / Takaful Malaysia (34)
    Berjaya Sompo Insurance (26)
- Concepts enabled strictly if present in company catalog; disabled otherwise.
- Baseline description set to company-specific description.

Usage:
    python commands/seed-canonical-79-benefits.py            # Dry-run
    python commands/seed-canonical-79-benefits.py --apply    # Execute DB commit
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sqlalchemy import select
from app.db.session import SessionLocal
from app.models.tables import (
    BenefitAlias,
    BenefitConcept,
    CompanyBenefitConfig,
    InsuranceCompany,
    new_id,
    utcnow,
)

# Canonical 1-79 numbering mapped to concept_key
MAPPING_79_TO_KEY: dict[int, str] = {
    1: "commercial-permitted-scope",
    2: "own-damage",
    3: "legal-costs-defense",
    4: "legal-representatives-indemnity",
    5: "loading-unloading-liability",
    6: "ncd-entitlement",
    7: "third-party-bi",
    8: "third-party-property",
    9: "towing-disabled-vehicle",
    10: "roadside-assistance",
    11: "towing",
    12: "auto-assistance",
    13: "agreed-value-market-value",
    14: "all-drivers",
    15: "betterment-scale",
    16: "betterment-protection",
    17: "repair-allowance",
    18: "cross-border",
    19: "enhanced-special-perils",
    20: "ferry-transit",
    21: "first-loss-flood",
    22: "car-detailing-cleanup",
    23: "out-of-pocket-allowance",
    24: "increased-tppd",
    25: "key-replacement",
    26: "legal-liability-of-passengers",
    27: "legal-liability-to-passengers",
    28: "ncd-relief",
    29: "vehicle-accessories",
    30: "special-perils",
    31: "strike-riot-civil-commotion",
    32: "repaint-spray-paint",
    33: "windscreen",
    34: "windscreen-auto-reinstatement",
    35: "boom-damage",
    36: "overturning",
    37: "attached-trailers",
    38: "cargo-protection",
    39: "gas-conversion-kit",
    40: "authorized-attendants",
    41: "temporary-bus-excursion",
    42: "tool-of-trade",
    43: "total-loss-theft-allowance",
    44: "flood-relief-allowance",
    45: "pa-worldwide-extension",
    46: "accidental-death",
    47: "ambulance-fees",
    48: "bereavement-allowance",
    49: "daily-hospital-income",
    50: "double-indemnity",
    51: "pa-medical-evacuation",
    52: "pa-facial-dental-surgery",
    53: "pa-family-scheme",
    54: "pa-insect-snake-bites",
    55: "pa-major-surgery",
    56: "medical-expenses",
    57: "permanent-disablement",
    58: "pa-post-hospital-recovery",
    59: "personal-belongings-theft",
    60: "ev-battery-depletion-towing",
    61: "ev-charging-bodily-injury",
    62: "ev-home-content-fire",
    63: "ev-home-charger-liability",
    64: "ev-wall-charger",
    65: "child-car-seat",
    66: "payd-telematics",
    67: "e-hailing-extension",
    68: "natural-falling-objects",
    69: "cashback-no-claim",
    70: "repair-workmanship-warranty",
    71: "side-mirror-protection",
    72: "document-replacement",
    73: "private-car-365",
    74: "commercial-driver-crew-pa",
    75: "driver-passenger-protector",
    76: "lonpac-ev-smart-pack",
    77: "motorshield-bundle",
    78: "motorcycle-pa-bundle",
    79: "sompo-motor-nhancer",
}


def normalize_phrase(phrase: str) -> str:
    """Normalize phrase for fuzzy indexing in benefit_aliases."""
    clean = re.sub(r"[^a-zA-Z0-9\s]", " ", phrase)
    return " ".join(clean.lower().split())


def load_canonical_benefits() -> list[dict[str, Any]]:
    """Parse docs/benefits/concise/all_benefits.md table."""
    all_benefits_file = ROOT / "docs" / "benefits" / "concise" / "all_benefits.md"
    results = []
    with open(all_benefits_file, "r", encoding="utf-8") as f:
        for line in f:
            line_str = line.strip()
            if line_str.startswith("|") and not line_str.startswith("| #") and not line_str.startswith("| :-:"):
                parts = [p.strip() for p in line_str.split("|")[1:-1]]
                if len(parts) >= 8:
                    try:
                        num = int(parts[0])
                        name = parts[1].replace("**", "").strip()
                        nature = parts[3].strip()
                        category = parts[4].strip()
                        desc = parts[6].strip()
                        aliases_raw = parts[7].strip()
                        results.append({
                            "num": num,
                            "name": name,
                            "nature": nature,
                            "category": category,
                            "description": desc,
                            "aliases_raw": aliases_raw,
                            "concept_key": MAPPING_79_TO_KEY[num],
                        })
                    except (ValueError, KeyError):
                        continue
    return results


def load_company_catalogs() -> dict[str, dict[str, Any]]:
    """Parse docs/benefits/concise/company_all_benefits-v4.md."""
    v4_file = ROOT / "docs" / "benefits" / "concise" / "company_all_benefits-v4.md"
    content = v4_file.read_text(encoding="utf-8")

    canonical_list = load_canonical_benefits()
    canonical_by_name = {c["name"].lower(): c for c in canonical_list}

    company_sections = re.split(r"###\s+([^\n]+?)\s+\((\d+)\s+Total Benefits\)", content)
    parsed = {}

    for i in range(1, len(company_sections), 3):
        c_name = company_sections[i].strip()
        target_count = int(company_sections[i + 1].strip())
        body = company_sections[i + 2]

        defaults_match = re.search(r"####\s+Defaults[^\n]*\n(.*?)(?=####\s+Add-ons|\Z)", body, re.DOTALL)
        addons_match = re.search(r"####\s+Add-ons[^\n]*\n(.*?)(?=---\Z|\Z)", body, re.DOTALL)

        def extract_items(text: str) -> list[tuple[str, str]]:
            items = []
            for line in text.strip().split("\n"):
                line = line.strip()
                m = re.match(r"^\d+\.\s+\*\*(.+?)\*\*\s+[—–-]\s*(.*)$", line)
                if m:
                    items.append((m.group(1).strip(), m.group(2).strip()))
            return items

        def_items = extract_items(defaults_match.group(1) if defaults_match else "")
        add_items = extract_items(addons_match.group(1) if addons_match else "")

        enabled_keys: dict[str, str] = {}  # concept_key -> custom_desc
        for name, desc in def_items + add_items:
            can = canonical_by_name.get(name.lower())
            if not can:
                for c_n, c_obj in canonical_by_name.items():
                    if c_n in name.lower() or name.lower() in c_n:
                        can = c_obj
                        break
            if can:
                enabled_keys[can["concept_key"]] = desc
            else:
                print(f"WARNING: Unmatched benefit '{name}' for {c_name}")

        parsed[c_name] = {
            "target_count": target_count,
            "enabled_keys": enabled_keys,
            "unique_count": len(enabled_keys),
        }

    return parsed


def seed_canonical_benefits(db, canonical_list: list[dict[str, Any]], dry_run: bool = True) -> tuple[list[str], list[str]]:
    """Seed / update benefit_concepts and benefit_aliases for all 79 benefits."""
    logs: list[str] = []
    new_concept_keys: list[str] = []

    existing_concepts = {c.concept_key: c for c in db.scalars(select(BenefitConcept)).all()}
    existing_aliases = {
        (a.benefit_id, a.normalized_phrase): a
        for a in db.scalars(select(BenefitAlias)).all()
    }

    for item in canonical_list:
        key = item["concept_key"]
        name = item["name"]
        desc = item["description"]
        num = item["num"]
        nature = item["nature"]
        category_kind = "default" if "Default" in nature else "addon"

        concept = existing_concepts.get(key)
        if not concept:
            # Create new BenefitConcept (default_asset_id = None)
            new_id_val = new_id()
            logs.append(f"[NEW CONCEPT #{num:02d}] {key} ({name}): '{desc}' (category={category_kind})")
            new_concept_keys.append(key)
            concept = BenefitConcept(
                id=new_id_val,
                concept_key=key,
                label=name,
                value_schema={"category": category_kind, "variants": []},
                display_template="{label}",
                required_variables=[],
                optional_variables=[],
                validation_rules={},
                default_asset_id=None,
                description=desc,
                demo_value=None,
                match_dataset=[],
                value_pattern_dataset=[],
                description_variants=[],
                display_overrides={},
                sort_order=num,
                revision=1,
                status="active",
                created_at=utcnow(),
                updated_at=utcnow(),
            )
            if not dry_run:
                db.add(concept)
            existing_concepts[key] = concept
        else:
            # Update existing BenefitConcept
            changes = []
            if concept.label != name:
                changes.append(f"label: '{concept.label}' -> '{name}'")
                if not dry_run:
                    concept.label = name
            if concept.description != desc:
                changes.append(f"desc: '{concept.description[:30]}...' -> '{desc[:30]}...'")
                if not dry_run:
                    concept.description = desc
            if concept.sort_order != num:
                changes.append(f"sort: {concept.sort_order} -> {num}")
                if not dry_run:
                    concept.sort_order = num
            if concept.status != "active":
                changes.append(f"status: {concept.status} -> active")
                if not dry_run:
                    concept.status = "active"
            schema = dict(concept.value_schema or {})
            if schema.get("category") != category_kind:
                changes.append(f"schema.category: {schema.get('category')} -> {category_kind}")
                if not dry_run:
                    schema["category"] = category_kind
                    concept.value_schema = schema

            if changes:
                logs.append(f"[UPDATE CONCEPT #{num:02d}] {key}: " + ", ".join(changes))
                if not dry_run:
                    concept.updated_at = utcnow()

        # Benefit Aliases
        if not dry_run and concept:
            db.flush()
            # Collect alias candidates
            alias_candidates = [name, key.replace("-", " ")]
            raw_aliases = item.get("aliases_raw", "")
            # remove *(+N more)*
            clean_raw = re.sub(r"\*\(\+\d+\s+more\)\*", "", raw_aliases)
            for part in clean_raw.split(";"):
                part_clean = part.strip()
                if part_clean and len(part_clean) > 2:
                    alias_candidates.append(part_clean)

            for cand in alias_candidates:
                norm = normalize_phrase(cand)
                if norm and (concept.id, norm) not in existing_aliases:
                    alias_obj = BenefitAlias(
                        id=new_id(),
                        benefit_id=concept.id,
                        phrase=cand,
                        normalized_phrase=norm,
                        scope="global",
                        company_id=None,
                        product_id=None,
                        package_id=None,
                        status="active",
                        created_at=utcnow(),
                        updated_at=utcnow(),
                    )
                    db.add(alias_obj)
                    existing_aliases[(concept.id, norm)] = alias_obj

    # Retire any concepts not in canonical 79
    canonical_keys_set = {item["concept_key"] for item in canonical_list}
    for c_key, c_obj in existing_concepts.items():
        if c_key not in canonical_keys_set and c_obj.status == "active":
            logs.append(f"[RETIRE OLD CONCEPT] {c_key} ({c_obj.label})")
            if not dry_run:
                c_obj.status = "retired"
                c_obj.updated_at = utcnow()

    if not dry_run:
        db.commit()

    return logs, new_concept_keys, existing_concepts


def seed_company_benefit_configs(
    db,
    canonical_list: list[dict[str, Any]],
    company_data: dict[str, dict[str, Any]],
    concepts_map: dict[str, BenefitConcept],
    dry_run: bool = True,
) -> list[str]:
    """Upsert CompanyBenefitConfig for all 7 insurers matching v4 counts."""
    logs: list[str] = []
    companies = list(db.scalars(select(InsuranceCompany)).all())
    concepts = concepts_map

    company_mapping = {
        "lonpac": "Lonpac Insurance",
        "etiqa": "Etiqa Insurance & Takaful",
        "tune-protect": "Tune Protect Insurance",
        "amassurance": "AmAssurance / Liberty Insurance",
        "qbe": "QBE Insurance",
        "takaful-malaysia": "STMB / Takaful Malaysia",
        "berjaya-sompo": "Berjaya Sompo Insurance",
    }

    for comp in companies:
        v4_name = company_mapping.get(comp.slug)
        if not v4_name:
            continue
        c_info = company_data.get(v4_name)
        if not c_info:
            print(f"WARNING: No v4 data found for {comp.name} ({comp.slug})")
            continue

        enabled_map = c_info["enabled_keys"]
        existing_cfgs = {
            cfg.concept_id: cfg
            for cfg in db.scalars(
                select(CompanyBenefitConfig).where(CompanyBenefitConfig.company_id == comp.id)
            ).all()
        }

        enabled_count = 0
        for item in canonical_list:
            key = item["concept_key"]
            concept = concepts.get(key)
            if not concept:
                continue

            is_enabled = key in enabled_map
            custom_desc = enabled_map.get(key) or concept.description or ""
            if is_enabled:
                enabled_count += 1

            cfg = existing_cfgs.get(concept.id)
            if not cfg:
                logs.append(f"[CONFIG ADD {comp.slug}] '{concept.label}' (enabled={is_enabled})")
                if not dry_run:
                    db.add(
                        CompanyBenefitConfig(
                            id=new_id(),
                            company_id=comp.id,
                            concept_id=concept.id,
                            is_enabled=is_enabled,
                            baseline_description=custom_desc,
                            created_at=utcnow(),
                            updated_at=utcnow(),
                        )
                    )
            else:
                updated = False
                if cfg.is_enabled != is_enabled:
                    logs.append(f"[CONFIG TOGGLE {comp.slug}] '{concept.label}' {cfg.is_enabled} -> {is_enabled}")
                    if not dry_run:
                        cfg.is_enabled = is_enabled
                        updated = True
                if cfg.baseline_description != custom_desc:
                    if not dry_run:
                        cfg.baseline_description = custom_desc
                        updated = True
                if updated and not dry_run:
                    cfg.updated_at = utcnow()

        # Ensure any non-canonical or retired concept config is disabled
        canonical_concept_ids = {
            concepts[item["concept_key"]].id
            for item in canonical_list
            if item["concept_key"] in concepts
        }
        for c_id, cfg in existing_cfgs.items():
            if c_id not in canonical_concept_ids and cfg.is_enabled:
                logs.append(f"[CONFIG DISABLE NON-CANONICAL {comp.slug}] Concept ID {c_id}")
                if not dry_run:
                    cfg.is_enabled = False
                    cfg.updated_at = utcnow()

        logs.append(
            f"[{comp.name} ({comp.slug})] Configured: {enabled_count} enabled / {len(canonical_list)} total "
            f"(target: {c_info['target_count']})"
        )

    if not dry_run:
        db.commit()

    return logs


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed canonical benefits and company configs.")
    parser.add_argument("--apply", action="store_true", help="Apply changes to the database.")
    args = parser.parse_args()

    canonical_list = load_canonical_benefits()
    print(f"Loaded {len(canonical_list)} canonical benefits from all_benefits.md")

    company_data = load_company_catalogs()
    print(f"Loaded {len(company_data)} company catalogs from company_all_benefits-v4.md\n")

    db = SessionLocal()
    try:
        print("=== Phase 1: Canonical 79 Benefits in benefit_concepts ===")
        c_logs, new_keys, concepts_map = seed_canonical_benefits(db, canonical_list, dry_run=not args.apply)
        print(f"Proposed concept log actions: {len(c_logs)}")
        for l in c_logs[:15]:
            print("  ", l)
        if len(c_logs) > 15:
            print(f"  ... and {len(c_logs) - 15} more concept actions.")
        print(f"Newly created concepts: {len(new_keys)}")

        print("\n=== Phase 2: Company Benefit Allocation in company_benefit_configs ===")
        cfg_logs = seed_company_benefit_configs(db, canonical_list, company_data, concepts_map, dry_run=not args.apply)
        summary_logs = [l for l in cfg_logs if "Configured:" in l]
        print(f"Company Pool Summaries ({len(summary_logs)} insurers):")
        for s in summary_logs:
            print("  *", s)

        if not args.apply:
            print("\n[DRY RUN COMPLETE] No database changes written. Pass --apply to execute.")
        else:
            print("\n[APPLY COMPLETE] Database updated successfully!")

    finally:
        db.close()


if __name__ == "__main__":
    main()
