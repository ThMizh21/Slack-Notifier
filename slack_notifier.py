import os
import requests
from dotenv import load_dotenv

from logger import logger

load_dotenv()

MAX_LISTED = 25


def send_slack(text: str) -> bool:
    webhook = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook:
        logger.warning("SLACK_WEBHOOK_URL not set; skipping Slack notification")
        return False

    try:
        resp = requests.post(webhook, json={"text": text}, timeout=10)
        resp.raise_for_status()
        logger.info("Slack notification sent")
        return True
    except requests.RequestException as exc:
        # Don't log the exception message: requests includes the URL,
        # and the webhook URL is a secret.
        status = getattr(exc.response, "status_code", None)
        logger.error("Slack notification failed: %s (status=%s)", type(exc).__name__, status)
        return False


def notify_inactive_report(result: dict, days: int) -> bool:
    emails = result["need_deactivation"]
    if not emails:
        logger.info("No accounts need deactivation; no Slack message sent")
        return False

    listed = "\n".join(f"• {e}" for e in emails[:MAX_LISTED])
    extra = len(emails) - MAX_LISTED
    if extra > 0:
        listed += f"\n…and {extra} more (see audit.log)"

    text = (
        f":warning: *Google Workspace inactive account review*\n"
        f"{len(emails)} active employee account(s) with no login for {days}+ days "
        f"or never logged in:\n{listed}\n\n"
        f"Inactive: {len(result['inactive_accounts'])} | "
        f"Never logged in: {len(result['never_logged_in_accounts'])}"
    )
    return send_slack(text)