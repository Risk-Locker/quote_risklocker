"""Security notification service for dispatching asynchronous security alerts."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)


def send_login_alert(
    user_email: str,
    ip_address: str | None,
    user_agent: str | None,
    timestamp: str | None = None,
) -> bool:
    """Dispatches a login security alert via the Resend API to the Master Admin."""
    api_key = os.getenv("RESEND_API_KEY", "").strip()
    recipient = os.getenv("SECURITY_ALERT_EMAIL", "system@risklocker.com").strip()
    from_email = os.getenv("RESEND_FROM_EMAIL", "RiskLocker Security <security@risklocker.com>").strip()

    if not api_key:
        logger.info(
            "RESEND_API_KEY is not configured. Security login alert for %s (IP: %s) skipped.",
            user_email,
            ip_address,
        )
        return False

    ts = timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    html_body = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 580px; margin: 0 auto; padding: 24px; border: 1px solid #e2e8f0; border-radius: 8px; background-color: #ffffff;">
        <div style="margin-bottom: 20px;">
            <span style="background-color: #fee2e2; color: #b91c1c; font-size: 11px; font-weight: bold; padding: 3px 8px; border-radius: 4px; text-transform: uppercase; letter-spacing: 0.05em;">Security Notice</span>
            <h2 style="color: #0f172a; margin: 12px 0 4px 0; font-size: 20px;">Successful Login Detected</h2>
            <p style="color: #64748b; font-size: 14px; margin: 0;">An authenticated login to RiskLocker was completed successfully.</p>
        </div>
        <table style="width: 100%; border-collapse: collapse; margin-top: 16px; font-size: 13px;">
            <tr>
                <td style="padding: 10px; font-weight: bold; color: #475569; width: 130px; border-bottom: 1px solid #f1f5f9; background-color: #f8fafc;">User Account:</td>
                <td style="padding: 10px; color: #0f172a; border-bottom: 1px solid #f1f5f9; font-weight: 600;">{user_email}</td>
            </tr>
            <tr>
                <td style="padding: 10px; font-weight: bold; color: #475569; border-bottom: 1px solid #f1f5f9; background-color: #f8fafc;">Client IP:</td>
                <td style="padding: 10px; color: #0f172a; border-bottom: 1px solid #f1f5f9; font-family: monospace;">{ip_address or "Unknown IP"}</td>
            </tr>
            <tr>
                <td style="padding: 10px; font-weight: bold; color: #475569; border-bottom: 1px solid #f1f5f9; background-color: #f8fafc;">Timestamp:</td>
                <td style="padding: 10px; color: #0f172a; border-bottom: 1px solid #f1f5f9;">{ts}</td>
            </tr>
            <tr>
                <td style="padding: 10px; font-weight: bold; color: #475569; border-bottom: 1px solid #f1f5f9; background-color: #f8fafc;">Device / Agent:</td>
                <td style="padding: 10px; color: #334155; font-size: 12px; font-family: monospace; border-bottom: 1px solid #f1f5f9; word-break: break-all;">{user_agent or "Unknown Agent"}</td>
            </tr>
        </table>
        <div style="margin-top: 24px; padding-top: 16px; border-top: 1px solid #e2e8f0; font-size: 12px; color: #94a3b8;">
            <p style="margin: 0;">If you did not authorize this login, please immediately access RiskLocker to revoke active sessions and update credentials.</p>
        </div>
    </div>
    """

    payload = {
        "from": from_email,
        "to": [recipient],
        "subject": f"[Security Alert] Successful Login Detected - {user_email}",
        "html": html_body,
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            if resp.status_code in {200, 201}:
                logger.info("Resend login alert dispatched to %s for %s", recipient, user_email)
                return True
            else:
                logger.warning("Resend API returned status %s: %s", resp.status_code, resp.text)
                return False
    except Exception as exc:
        logger.error("Failed to dispatch Resend login alert: %s", exc)
        return False
