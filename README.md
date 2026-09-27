# Job Application Toolkit — Setup Guide

Fetches jobs (Adzuna API), filters by your salary floor + experience, drafts
a tailored cover letter for each match (Claude API), and tracks what you've
applied to — all running automatically once a day. You still click "Apply"
yourself on each listing (see "Why no auto-submit?" below).

## Files in this toolkit

| File | Purpose |
|---|---|
| `job_matcher_demo.py` | Core scoring logic + your `SKILLS_VOCAB`. Other scripts import from here. |
| `job_matcher_live.py` | Adzuna API fetcher, your resume text, search config (keywords/locations/salary). |
| `job_apply_bulk.py` | **Main daily driver.** Filters jobs by salary + experience, drafts cover letters, writes the report, logs to CSV. |
| `job_daily_apply.py` | Alternate version: ranks jobs by fit score instead of a pass/fail filter. Not used by cron by default. |
| `mark_applied.py` | CLI: mark a job as applied by typing a search term. |
| `dashboard.py` | Local web UI: click a button to mark a job as applied instead. |
| `cron_job.sh` | Wrapper script cron calls — handles logging and working directory. |
| `.gitignore` | Keeps `.env` out of version control. |
| `requirements.txt` | All Python dependencies in one place. |
| `applications_log.csv` | Generated automatically — your running application tracker. |
| `bulk_apply_YYYY-MM-DD.md` | Generated daily — that day's filtered job list + drafts. |

## One-time setup

```bash
# 1. Install dependencies
pip install -r requirements.txt --break-system-packages

# 2. Set up your API keys
create .env file
# then edit .env and fill in:
#   ADZUNA_APP_ID=...       (from developer.adzuna.com)
#   ADZUNA_APP_KEY=...
#   ANTHROPIC_API_KEY=...   (from console.anthropic.com)

# 3. Make the cron wrapper executable
chmod +x cron_job.sh

# 4. Do a manual test run first
./cron_job.sh
cat bulk_apply_*.md      # check the output looks right
cat cron.log             # check for errors
```

Before scheduling, double check in `job_matcher_live.py`:
- `SEARCH_KEYWORDS` — your target role titles
- `SEARCH_LOCATIONS` — your target cities
- `DESIRED_SALARY` — your target (used for display in the ranked/daily version)
- `MY_RESUME` — your resume text

And in `job_daily_apply.py`:
- `MIN_ACCEPTABLE_SALARY` — your hard floor (currently ₹15,00,000)
- `MY_YEARS_EXPERIENCE` / `EXPERIENCE_BUFFER` — your experience filter
- `MAX_DRAFTS` — cap on Claude API calls per run (cost control)

## Scheduling the daily run (cron)

Open your crontab:
```bash
crontab -e
```

Add this line (runs every morning at 8:00 AM — adjust the time as you like):
```
0 8 * * * /full/path/to/this/folder/cron_job.sh
```

Use the **absolute path** to the folder — cron does not know your current
directory. Find it with `pwd` while standing inside the folder.

Save and exit. Verify it's registered:
```bash
crontab -l
```

That's it — every morning, a fresh `bulk_apply_YYYY-MM-DD.md` will appear in
this folder, and new jobs will be appended to `applications_log.csv`. Check
`cron.log` if a run seems to have failed silently (e.g. expired API key,
Adzuna rate limit hit).

## Your daily workflow

1. Open the newest `bulk_apply_YYYY-MM-DD.md`
2. For each job: click the apply link, review/tweak the draft cover letter, submit
3. Run `python3 dashboard.py` (or use `mark_applied.py`) to mark it applied
4. Repeat down the list

## Why no auto-submit?

LinkedIn, Naukri, Indeed, and most company career sites (Workday, Greenhouse,
Lever, etc.) explicitly prohibit automated form submission in their Terms of
Service, and none offer an API for it. The only technical way around that is
browser automation impersonating a human — which risks account bans and can
get applications auto-rejected by the same anti-bot systems it's trying to
bypass. This toolkit automates everything *up to* that point (search,
filter, draft) and leaves the final click to you, which keeps every account
involved safe.

## Maintenance notes

- Adzuna's free tier has a daily request cap. With 10 keywords × 3 locations,
  each run makes 30 API calls — watch `cron.log` for rate-limit errors if you
  widen either list further.
- `SKILLS_VOCAB` in `job_matcher_demo.py` should be updated if your resume or
  target roles change significantly — it's a hardcoded keyword list, not
  auto-extracted.
- If Claude's API changes its model naming, update `CLAUDE_MODEL` in
  `job_matcher_bulk.py` (check docs.claude.com for current model strings).
