from logger import logger, audit_logger
from slack_notifier import send_slack, notify_inactive_report


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


def main():
    try:
        result = inactive_accounts()
    except Exception as exc:
        logger.exception("Inactive account scan failed")
        send_slack(f":x: Google Workspace inactive account scan failed: {type(exc).__name__}. Check web_log.log / db.log.")
        raise SystemExit(1)

    notify_inactive_report(result, INACTIVE_DAYS)


if __name__ == "__main__":
    main()