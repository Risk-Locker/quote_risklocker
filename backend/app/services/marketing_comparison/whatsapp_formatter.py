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
        motor_p = float(e.get("rounded_motor_premium") if e.get("rounded_motor_premium") is not None else round(e.get("motor_premium", 0.0)))
        tot_p = float(e.get("rounded_total_payable") if e.get("rounded_total_payable") is not None else round(e.get("total_payable", 0.0)))
        disc = float(e.get("effective_discount") or 0.0)
        net_p = float(e.get("rounded_net_total_payable") if e.get("rounded_net_total_payable") is not None else max(0.0, tot_p - round(disc)))

        if disc > 0.0:
            payable_lines = [
                f"   • Total Payable: RM {tot_p:,.2f}",
                f"   • Discount: - RM {disc:,.2f}",
                f"   • *NET TOTAL PAYABLE: RM {net_p:,.2f}*",
            ]
        else:
            payable_lines = [
                f"   • *TOTAL PAYABLE: RM {tot_p:,.2f}*",
            ]

        lines.extend([
            f"*{idx}. {e['company_name']}{rec_tag}*",
            f"   • Sum Insured: RM {e['sum_insured']:,.2f} ({val_tag})",
            f"   • Motor Insurance: RM {motor_p:,.2f}",
            *payable_lines,
            f"   • Towing: {e['towing_limit']}",
            f"   • Waiver of Betterment: {betterment_tag} | Excess: RM {e['excess']:.2f}",
            "",
        ])

    lines.append("━━━━━━━━━━━━━━━━━━━━━━")

    rec_winners = [e for e in entries if e.get("is_recommended")]
    if len(rec_winners) == 1:
        w = rec_winners[0]
        w_disc = float(w.get("effective_discount") or 0.0)
        if w_disc > 0.0:
            win_net = float(w.get("rounded_net_total_payable") if w.get("rounded_net_total_payable") is not None else max(0.0, float(w.get("total_payable", 0.0)) - w_disc))
            lines.append(
                f"🏆 *Recommended Choice:* {w['company_name']} (Net: RM {win_net:,.2f})\n"
            )
        else:
            win_tot = float(w.get("rounded_total_payable") if w.get("rounded_total_payable") is not None else round(w.get("total_payable", 0.0)))
            lines.append(
                f"🏆 *Recommended Choice:* {w['company_name']} (Total: RM {win_tot:,.2f})\n"
            )
    elif len(rec_winners) > 1:
        winner_items = []
        for w in rec_winners:
            w_disc = float(w.get("effective_discount") or 0.0)
            if w_disc > 0.0:
                w_val = float(w.get("rounded_net_total_payable") if w.get("rounded_net_total_payable") is not None else max(0.0, float(w.get("total_payable", 0.0)) - w_disc))
                winner_items.append(f"{w['company_name']} (Net RM {w_val:,.2f})")
            else:
                w_val = float(w.get("rounded_total_payable") if w.get("rounded_total_payable") is not None else round(w.get("total_payable", 0.0)))
                winner_items.append(f"{w['company_name']} (RM {w_val:,.2f})")
        lines.append(f"🏆 *Shortlisted Options ({len(rec_winners)}):* {', '.join(winner_items)}\n")

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
