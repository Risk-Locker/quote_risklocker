"""WhatsApp Teaser Formatter for Underwriter Marketing Comparison."""

from __future__ import annotations

from typing import Any, Callable
from sqlalchemy.orm import Session


def format_whatsapp_teaser_from_data(data: dict[str, Any]) -> str:
    """Format a clean, executive WhatsApp teaser message from raw comparison data dict."""
    tenure = data["tenure"]
    entries = data["entries"]

    plate = tenure["vehicle_no"]
    customer = tenure["customer_name"]
    model = tenure["vehicle_model"]
    period = tenure["coverage_period_formatted"]
    ncd = tenure.get("ncd_percentage")
    ncd_str = f"{ncd:.0f}%" if ncd is not None else "Not Detected"

    lines = [
        f"🚗 *Insurance Renewal Comparison for {plate}*",
        f"👤 Customer: {customer}",
        f"🚘 Vehicle: {model} ({tenure['engine_cc']})",
        f"📅 Period: {period} | NCD: {ncd_str}",
        f"🛣️ Roadtax and Runner fee : RM {tenure['fixed_costs_total']:.2f}",
        "",
        "📋 *UNDERWRITER COMPARISON:*",
        "━━━━━━━━━━━━━━━━━━━━━━",
    ]

    for idx, e in enumerate(entries, 1):
        rec_tag = " ★ (RECOMMENDED)" if e.get("is_recommended") else ""
        val_tag = "Agreed Value" if e.get("agreed_value") else "Market Value"
        betterment_tag = "Yes" if e.get("waiver_betterment") else "No"

        lines.extend([
            f"*{idx}. {e['company_name']}{rec_tag}*",
            f"   • Sum Insured: RM {e['sum_insured']:,.2f} ({val_tag})",
            f"   • Motor Insurance: RM {e['motor_premium']:,.2f}",
            f"   • *TOTAL PAYABLE: RM {e['total_payable']:,.2f}*",
            f"   • Towing: {e['towing_limit']}",
            f"   • Waiver of Betterment: {betterment_tag} | Excess: RM {e['excess']:.2f}",
            "",
        ])

    lines.append("━━━━━━━━━━━━━━━━━━━━━━")

    rec_winners = [e for e in entries if e.get("is_recommended")]
    if len(rec_winners) == 1:
        lines.append(
            f"🏆 *Recommended Choice:* {rec_winners[0]['company_name']} (Total: RM {rec_winners[0]['total_payable']:,.2f})\n"
        )
    elif len(rec_winners) > 1:
        winner_items = ", ".join(
            f"{w['company_name']} (RM {w['total_payable']:,.2f})" for w in rec_winners
        )
        lines.append(f"🏆 *Shortlisted Options ({len(rec_winners)}):* {winner_items}\n")

    lines.append(
        "💡 *Please let us know your preferred insurer so we can issue your official Risk-Locker quotation!*"
    )

    return "\n".join(lines)


def format_whatsapp_teaser(
    db: Session,
    tenure_id: str,
    get_comparison_fn: Callable[[Session, str], dict[str, Any]],
) -> str:
    """Format a clean, executive WhatsApp teaser message comparing all underwriters for client messaging."""
    data = get_comparison_fn(db, tenure_id)
    return format_whatsapp_teaser_from_data(data)
