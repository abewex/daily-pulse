# daily-pulse

Builds "Abe's Daily Pulse" (14-page, 3.6x4.8" Kindle PDF) and emails it to Kindle on weekdays.

- `builder/pulse.py` - turns a day's `data.json` into the PDF (no personal data in the repo).
- `RUNBOOK.md` - what the 7am Claude scheduled task does each morning.
- `.github/workflows/send-to-kindle.yml` - emails the PDF when it's pushed to the `outbox` branch (or `outbox-test` for tests), then deletes the branch.

Repo secrets (Settings > Secrets and variables > Actions): `GMAIL_USERNAME`, `GMAIL_APP_PASSWORD`, `KINDLE_EMAIL`, optional `TEST_EMAIL` (defaults to `GMAIL_USERNAME`).
