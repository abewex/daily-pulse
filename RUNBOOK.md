# The Pulse — daily run book

Followed by the weekday 6:45 ET scheduled task. Goal: a 14-page Kindle PDF in Abe's inbox-to-Kindle by 7:00 ET.

## Hard rules
- **WealthPosition is read-only.** Use only `account_balances`, `transactions`, `chart_of_accounts`, `payees`, `tags`. Never call `save_*` or `delete_*`.
- **Never commit personal data to `main`.** The day's `data.json` stays in the scratch directory. The only thing pushed is the PDF, to the `outbox` branch, which the workflow deletes after sending.
- **Never embed secrets** in prompts, files or commits. Sending happens in GitHub Actions using repo secrets.
- **Label gaps, don't fake them.** If a number or story can't be sourced today, say so on the page.
- Don't re-send if `outbox` already exists on the remote (a previous run is mid-send or failed); report it instead.

## 1. Pull the ledger (WealthPosition)
- `account_balances` for today and for each of the last 5 month-ends.
- `transactions` for month-to-date and for the full previous month (paginate: 100 per page; check `count`).
- Classify each entry:
  - Two-sided with an `E` leg → `expenses_mtd` / `expenses_prev_month` as `[date, category, amount]` (spend negative, reimbursement positive).
  - Single `L` entry on a card (uncategorized charge) → `uncategorized_mtd` as `[label, amount, date]`.
  - Uncategorized Venmo inflows that clearly reimburse a listed charge → `uncategorized_offsets` `[label, amount]`.
  - `I` legs (prev month) → `income_prev_month` totals by type.
- Copy numbers carefully. After writing `data.json`, re-read every balance and spot-check 10 transactions against the tool output.

## 2. Gather news (fresh every morning, every item with a real tappable URL)
Search separately for each: market close (latest session), Treasury yields/curve + week-ahead calendar, Apple (Gurman/Power On, supply chain, analyst notes), HFT/market structure (HRT, Jane Street, Citadel Securities, venues, SEC/Reg NMS), CPA/accounting (FASB, PCAOB, SEC, AICPA, deadlines), NYC (MTA service/policy, Yorkville/10128 hyperlocal; Rochester only if relevant), and 3 commute reads (5–8 min) with "why it matters".

## 3. Write `data.json` (schema = `examples/sample.json`)
Narrative blocks: `{"type": "h2"|"p"|"note"|"bullet"|"table"|"space", "text": ...}`. Text is ReportLab markup: `<b>`, `<i>`, `<a href="URL" color="#1a4b8c"><u>src</u></a>`; escape `&` as `&amp;`. Tables: `{"type":"table","rows":[[...]],"widths":[fractions summing to 1]}`.

Keys: `delta` (2 bullets: yield shift; top HFT/Apple leak — spend pace bullet is auto-generated), `auditor_callouts` (max 3), `markets`, `rates` (include a Bond Literacy block), `tech_apple`, `industry` (HFT half + CPA half), `nyc`, `commute_reads`, `audit_flags`, `methodology` (today's specific limits).

Voice: numbers-native, terse, proper accounting lingo, never cringe. Show the math. Each page must fit one Kindle screen — the builder shrinks overflow, so keep each page to roughly 8–10 short items.

## 4. Build and check
```
python3 builder/pulse.py <scratch>/data.json <scratch>/out
```
Then: confirm 14 pages, render pages 1, 2 and 5 to PNG and look at them (nothing blank, no overflowed tiny text, links present), and check the printed totals match the ledger.

## 5. Send
The send branch must start from `main` (GitHub reads the workflow file from the pushed branch).
```
cd <clone>; git fetch origin main
git ls-remote --exit-code --heads origin outbox && echo "outbox exists - stop and report"
git checkout -B outbox origin/main
cp <scratch>/out/Abes_Daily_Pulse_*.pdf . && git add -f Abes_Daily_Pulse_*.pdf
git commit -qm "Pulse $(date +%F)" && git push origin outbox
git checkout main && git branch -D outbox && rm -f Abes_Daily_Pulse_*.pdf
```
Use branch `outbox-test` instead of `outbox` for any test (goes to TEST_EMAIL, not the Kindle).

Then watch the "Send Pulse to Kindle" Actions run (`gh api repos/abewex/daily-pulse/actions/runs?per_page=1`). Job logs aren't readable from the session; read the reason from the job's check-run annotations (`gh api repos/abewex/daily-pulse/check-runs/<job id>/annotations`). This session can't delete remote branches; the workflow deletes `outbox` itself after every attempt, success or failure. Report success or the failure reason in one line, and send the PDF to Abe in the conversation either way.
