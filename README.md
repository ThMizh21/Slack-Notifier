# Slack Notifier – Google Workspace Inactive Account Alerts

Scans a Google Workspace domain for accounts that haven't logged in for a configurable number of days (or never logged in), cross-checks them against an HR/employee MySQL database, and posts a Slack message listing **active employees whose Google accounts look dormant** so they can be reviewed for deactivation.

## How it works

1. Authenticates to the Google Admin SDK with a service account (domain-wide delegation, impersonating `ADMIN_EMAIL`).
2. Collects accounts whose last login is older than `INACTIVE_DAYS`, plus accounts that never logged in.
3. Queries the `employees` table in MySQL (in batches) and keeps only emails with `status = 'Active'`.
4. Writes each flagged account to the audit log and sends a summary to Slack via an incoming webhook (first 25 listed, the rest in `audit.log`).
5. If the scan fails, a failure notice is sent to Slack and the process exits with code 1.

No Slack message is sent when nothing needs review.

## Project layout

| File | Purpose |
|---|---|
| `main.py` | Orchestrates the scan, DB filtering and notification |
| `slack_notifier.py` | Slack webhook posting and report formatting |
| `database.py` | MySQL connection helper |
| `logger.py` | Rotating file loggers (`web_log.log`, `db.log`, `audit.log`) |
| `.env.example` | Template for required configuration |

## Setup

Requires Python 3.9+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then edit values
```

### Configuration (`.env`)

| Variable | Description |
|---|---|
| `KEY_PATH` | Path to the service account JSON key (keep out of git) |
| `ADMIN_EMAIL` | Super admin the service account impersonates |
| `INACTIVE_DAYS` | Days without login before an account is flagged |
| `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` | MySQL connection (a read-only user is sufficient) |
| `SLACK_WEBHOOK_URL` | Slack incoming webhook (tied to one channel) |

### Google prerequisites

- A service account with domain-wide delegation enabled.
- The Admin SDK Directory API enabled, and the delegation client ID authorized in the Admin console with a read-only user scope.

### Database expectations

An `employees` table with `employee_email` and `status` columns (`'Active'` for current employees).

## Usage

```bash
python main.py
```

Suitable for running on a schedule, e.g. with cron:

```cron
0 9 * * 1  cd /path/to/Slack-Notifier && .venv/bin/python main.py
```

## Logs

Written to `logs/` with rotation (5 MB per file):

- `web_log.log` – general application log
- `db.log` – database connection activity
- `audit.log` – accounts flagged for deactivation review (30 backups kept)

## Security notes

- The webhook URL is a secret; errors are logged without the request URL.
- This tool only **reports** accounts; it does not suspend or delete anything.
