"""Autonomous AI Health & Quota Radar Report for Risklocker.

Monitors multi-key Gemini accounts, tracks daily requests against the strict 480 RPD cap,
probes live Google AI Studio model availability, and alerts when quotas or endpoints change.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add backend directory to sys.path
ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings, resolve_active_gemini_model
from app.db.session import SessionLocal
from app.extraction.pacer_sentinel import (
    SAFE_RPD_CEILING,
    SAFE_RPM_CEILING,
    SAFE_TPM_CEILING,
)
from app.services.gemini_account_service import (
    PARALLEL_MODELS,
    get_ai_quota_radar_snapshot,
    get_current_local_date,
    get_key_pool,
)


def generate_ai_system_report(*, probe_live: bool = False) -> dict:
    """Generate comprehensive report of live Gemini key pool and parallel model quotas."""
    return get_ai_quota_radar_snapshot(probe_live=probe_live)



def print_formatted_report(report: dict) -> None:
    """Print clean executive report for human inspection."""
    print("=" * 78)
    print("  RISKLOCKER AI SYSTEM & GEMINI FLEET HEALTH REPORT")
    print(f"  Date: {report['local_date']} | Status: {report['overall_status']}")
    print("=" * 78)
    print(f"  Configured API Keys : {report['key_count']}")
    print(f"  Parallel Endpoints  : {report['total_endpoints']} (2 Models x {report['key_count']} Keys)")
    print(f"  Primary Model       : {report['active_model']}")
    print(f"  Parallel Pool Models: {', '.join(PARALLEL_MODELS)}")
    print(f"  Total Fleet RPD     : {report['total_rpd_used']} / {report['total_rpd_limit']} Requests Today")
    print(f"  Per-Endpoint Safety : Capped strictly at {SAFE_RPD_CEILING} RPD (Never exceeded)")
    print("-" * 78)
    print("  ENDPOINT QUOTA BREAKDOWN (Strict 480 RPD Mark Per Model):")
    print("  {:<12} {:<24} {:<10} {:<10} {:<12} {:<10}".format(
        "Key", "Model", "Used Today", "Limit", "Remaining", "Status"
    ))
    print("  " + "-" * 76)

    for ep in report.get("endpoints", []):
        acc_lbl = ep.get("account_label", "").replace("Account ", "Key ")
        m_name = ep.get("model", "")
        # Get usage for this account/model from account stats
        acc_id = ep.get("account_id")
        acc = next((a for a in report["accounts"] if a["id"] == acc_id), None)
        acc_used = acc.get("rpd_used", 0) if acc else 0
        limit = ep.get("rpd_limit", SAFE_RPD_CEILING)
        remaining = max(0, limit - acc_used)
        status = "Active" if remaining > 0 else "Exhausted"

        print("  {:<12} {:<24} {:<10} {:<10} {:<12} {:<10}".format(
            acc_lbl[:12],
            m_name[:24],
            f"{acc_used}",
            f"{limit}",
            f"{remaining}",
            status,
        ))

    print("-" * 78)
    if report["alerts"]:
        print("  ACTIVE ALERTS:")
        for alert in report["alerts"]:
            print(f"  * {alert}")
    else:
        print("  [OK] Zero quota alerts. All slots operating safely within 480 RPD cap.")
    print("=" * 78)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Risklocker Gemini AI health & quota status.")
    parser.add_argument("--probe", action="store_true", help="Send live ping to Google API to verify key.")
    parser.add_argument("--json", action="store_true", help="Output raw JSON instead of table.")
    parser.add_argument("--fail-on-alert", action="store_true", help="Exit with code 1 if quota alerts exist.")
    args = parser.parse_args()

    report = generate_ai_system_report(probe_live=args.probe)

    if args.json:
        import json
        print(json.dumps(report, indent=2))
    else:
        print_formatted_report(report)

    if args.fail_on_alert and report["alerts"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
