import os
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build

from database import create_db_connection
from logger import logger, audit_logger
from slack_notifier import send_slack, notify_inactive_report

load_dotenv()

INACTIVE_DAYS = int(os.getenv("INACTIVE_DAYS", "60"))
BATCH_SIZE = 500
SCOPES = ["https://www.googleapis.com/auth/admin.directory.user.readonly"]


def get_admin_service():
    creds = service_account.Credentials.from_service_account_file(
        os.getenv("KEY_PATH"), scopes=SCOPES, subject=os.getenv("ADMIN_EMAIL")
    )
    return build("admin", "directory_v1", credentials=creds, cache_discovery=False)


def fetch_candidate_emails(service, cutoff):
    """Return (inactive, never_logged_in) lowercase emails for non-suspended users."""
    inactive, never = [], []
    page_token = None
    while True:
        resp = service.users().list(
            customer="my_customer",
            maxResults=500,
            orderBy="email",
            pageToken=page_token,
            fields="nextPageToken,users(primaryEmail,lastLoginTime,suspended)",
        ).execute()
        for user in resp.get("users", []):
            if user.get("suspended"):
                continue
            email = user["primaryEmail"].lower()
            last = user.get("lastLoginTime")
            # Google reports 1970-01-01 for accounts that never logged in
            if not last or last.startswith("1970-01-01"):
                never.append(email)
            elif datetime.fromisoformat(last.replace("Z", "+00:00")) < cutoff:
                inactive.append(email)
        page_token = resp.get("nextPageToken")
        if not page_token:
            return inactive, never


def filter_active_employees(emails):
    connection = create_db_connection()
    if not connection:
        raise RuntimeError("Failed to connect with DB")

    active = []
    try:
        cursor = connection.cursor()
        for i in range(0, len(emails), BATCH_SIZE):
            chunk = emails[i:i + BATCH_SIZE]
            placeholders = ",".join(["%s"] * len(chunk))
            cursor.execute(
                f"""
                SELECT LOWER(employee_email)
                FROM employees
                WHERE status = 'Active'
                  AND LOWER(employee_email) IN ({placeholders})
                """,
                chunk,
            )
            active.extend(row[0] for row in cursor.fetchall())
        cursor.close()
    finally:
        connection.close()

    logger.info("DB check: %d of %d candidates are Active employees", len(active), len(emails))
    return active


def inactive_accounts():
    logger.info("Inactive account scan started (threshold: %d days)", INACTIVE_DAYS)

    service = get_admin_service()
    cutoff = datetime.now(timezone.utc) - timedelta(days=INACTIVE_DAYS)
    logger.info("Cutoff date: %s", f"{cutoff:%Y-%m-%d}")

    inactive, never = fetch_candidate_emails(service, cutoff)
    logger.info("Google scan done: %d inactive, %d never logged in", len(inactive), len(never))

    emails = list(dict.fromkeys(inactive + never))
    need_deactivation = filter_active_employees(emails) if emails else []

    for email in need_deactivation:
        audit_logger.info("FLAGGED for deactivation review: %s", email)

    logger.info("Scan complete: %d accounts need deactivation review", len(need_deactivation))

    return {
        "inactive_accounts": inactive,
        "never_logged_in_accounts": never,
        "need_deactivation": need_deactivation,
    }

def db_health():
    project_ref = os.getenv("SUPABASE_PROJECT_REF")
    access_token = os.getenv("SUPABASE_ACCESS_TOKEN")
    resp = request.get(
        f"https://api.supbase.com/v1/projects/{project_ref}",
        headers={"Authorization":f"Bearer {access_token}"}
    )

    resp.raise_for_status()
    status = resp.json().get("status")
    logger.info("Supabase project status: %s", status)

    if status and status not in {"ACTIVE_HEALTHY", "COMING_UP"}:
        send_slack(f":rotating_light: Supabase project status is '{status}' (may be paused).")
    return status

def main():
    try:
        result = inactive_accounts()
    except Exception as exc:
        logger.exception("Inactive account scan failed")
        send_slack(f":x: Google Workspace inactive account scan failed: {type(exc).__name__}. Check web_log.log / db.log.")
        raise SystemExit(1)

    notify_inactive_report(result, INACTIVE_DAYS)

    try:
        db_health()
    except requests.RequestException as exc:
        # Don't log the exception message: it may contain the project URL.
        logger.error("Supabase health check failed: %s", type(exc).__name__)
        send_slack(f":x: Supabase health check failed: {type(exc).__name__}.")

if __name__ == "__main__":
    main()
