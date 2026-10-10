# Slack Notifier – Google Workspace Inactive Account Alerts & Supabase Health Check

Scans a Google Workspace domain for accounts that haven't logged in for a configurable number of days (or never logged in), cross-checks them against an HR/employee MySQL database, and posts a Slack message listing **active employees whose Google accounts look dormant** so they can be reviewed for deactivation.

## How it works

1. Authenticates to the Google Admin SDK with a service account (domain-wide delegation, impersonating `ADMIN_EMAIL`).
2. Collects accounts whose last login is older than `INACTIVE_DAYS`, plus accounts that never logged in.
3. Queries the `employees` table in MySQL (in batches) and keeps only emails with `status = 'Active'`.
4. Writes each flagged account to the audit log and sends a summary to Slack via an incoming webhook (first 25 listed, the rest in `audit.log`).
5. If the scan fails, a failure notice is sent to Slack and the process exits with code 1.

6. After the report, checks the Supabase project status through the Supabase Management API and alerts Slack if the project is not `ACTIVE_HEALTHY` or `COMING_UP` (e.g. paused).

No Slack message is sent when nothing needs review and Supabase is healthy.

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
| `SUPABASE_PROJECT_REF` | Supabase project reference ID, used for the project status check |
| `SUPABASE_ACCESS_TOKEN` | Supabase personal access token for the Management API |

### Google prerequisites

- A service account with domain-wide delegation enabled.
- The Admin SDK Directory API enabled, and the delegation client ID authorized in the Admin console with a read-only user scope.

### Database expectations

An `employees` table with `employee_email` and `status` columns (`'Active'` for current employees).

## Supabase monitoring: what is and isn't possible

`db_health()` in `main.py` only checks the **project status** (`GET /v1/projects/{ref}`). Supabase exposes **no API** that returns:

- **egress (bandwidth) usage**, or
- **active user count**.

These can't be polled, so they have to be measured by the application itself:

- **Egress usage** – wrap the Supabase client / HTTP layer in a wrapper that adds up the size of every response (e.g. `Content-Length` or `len(response.content)`), keeps a running total per billing period, and triggers a Slack notification when the total approaches the plan limit (e.g. at 80% / 90%).
- **Active user count** – track it in the app (e.g. record a user's ID/last-seen on login or request and count distinct users in the period), and send a Slack alert when the count approaches the plan's limit.

Both figures are therefore app-side estimates and may differ slightly from what Supabase bills. This is not implemented yet.

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

- `web_log.log` – general application log (including Supabase status)
- `db.log` – database connection activity
- `audit.log` – accounts flagged for deactivation review (30 backups kept)

## Security notes

- The webhook URL is a secret; errors are logged without the request URL.
- This tool only **reports** accounts; it does not suspend or delete anything.
