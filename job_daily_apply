"""
Job Matcher — Daily Shortlist Generator
------------------------------------------
Runs the full pipeline:
  1. Fetch live jobs (Adzuna API)
  2. Rank by resume-skill overlap + salary fit (job_matcher_live.py logic)
  3. For jobs clearing FIT_THRESHOLD, generate a tailored cover-letter draft
     using the Claude API
  4. Write everything to a dated Markdown report which we can  apply in a few clicks.

SETUP:

  .env file needs:
    ADZUNA_APP_ID=...
    ADZUNA_APP_KEY=...
    ANTHROPIC_API_KEY=...    

Run manually:
  python3 job_daily_apply.py

"""

import os
from datetime import datetime

from dotenv import load_dotenv

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None  

from job_matcher_live import (
    ADZUNA_APP_ID,
    ADZUNA_APP_KEY,
    ADZUNA_COUNTRY,
    SEARCH_KEYWORDS,
    SEARCH_LOCATIONS,
    RESULTS_PER_PAGE,
    NUM_PAGES,
    DESIRED_SALARY,
    MY_RESUME,
    fetch_adzuna_jobs_multi,
    rank_jobs_live,
)
from job_matcher_demo import DEMO_JOBS


load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = "claude-sonnet-5"  # check docs.claude.com/en/docs/about-claude/models for current options

# Only generate a drafted cover letter for jobs scoring at or above this —
# keeps API cost down and avoids wasting drafts on poor-fit roles.
FIT_THRESHOLD = 7.0

# Cap how many drafts get generated per run (safety limit on API spend)
MAX_DRAFTS = 10


# ---------------------------------------------------------------------------
# COVER LETTER GENERATION
# ---------------------------------------------------------------------------

def generate_cover_letter(client: Anthropic, resume_text: str, job) -> str:
    """
    Calls the Claude API to draft a short, tailored cover letter for one job.
    Returns plain text the user can review and paste into an application.
    """
    prompt = f"""You are helping a job applicant draft a short cover letter.

RESUME:
{resume_text.strip()}

JOB TITLE: {job.title}
COMPANY: {job.company}
MATCHED SKILLS: {', '.join(sorted(job.matched_skills)) or 'none clearly listed'}

Write a concise, natural-sounding cover letter (150-200 words) tailored to
this role. Reference 2-3 concrete points of overlap between the resume and
the role. Avoid generic filler phrases ("I am writing to express my
interest..."). Do not invent experience not present in the resume. End with
a simple, confident closing line — no "Sincerely, [Your Name]" placeholder
needed, the user will add their own signature."""

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        # Claude Sonnet 5 can return a thinking block ahead of the text
        # block, so don't assume content[0] is the text — find it by type.
        text_blocks = [b.text for b in response.content if getattr(b, "type", None) == "text"]
        return text_blocks[0].strip() if text_blocks else "[No text content returned]"
    except Exception as e:
        return f"[Draft generation failed: {e}]"


# ---------------------------------------------------------------------------
# REPORT WRITING
# ---------------------------------------------------------------------------

def write_report(ranked_jobs, drafts: dict, filepath: str):
    lines = []
    lines.append(f"# Daily Job Shortlist — {datetime.now().strftime('%Y-%m-%d')}\n")
    lines.append(f"Search: \"{SEARCH_KEYWORDS}\" in {SEARCH_LOCATIONS} | "
                 f"Desired salary: ₹{DESIRED_SALARY:,}\n")
    lines.append("---\n")

    for i, job in enumerate(ranked_jobs, 1):
        lines.append(f"## {i}. {job.title} — {job.company}\n")
        lines.append(f"- **Final score:** {job.final_score}/10")
        lines.append(f"- **Resume fit:** {job.resume_score}/10")
        lines.append(f"- **Salary fit:** {job.salary_score}/10 ({job.salary_note})")
        if job.matched_skills:
            lines.append(f"- **Matched skills:** {', '.join(sorted(job.matched_skills))}")
        if job.missing_skills:
            lines.append(f"- **Missing skills:** {', '.join(sorted(job.missing_skills))}")
        url = getattr(job, "url", "")
        if url:
            lines.append(f"- **Apply here:** {url}")

        draft = drafts.get(job.title + job.company)
        if draft:
            lines.append("\n**Draft cover letter (review before using):**\n")
            lines.append("> " + draft.replace("\n", "\n> "))

        lines.append("\n---\n")

    with open(filepath, "w") as f:
        f.write("\n".join(lines))


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # 1. Fetch jobs
    if ADZUNA_APP_ID and ADZUNA_APP_KEY:
        jobs = fetch_adzuna_jobs_multi(
            ADZUNA_APP_ID, ADZUNA_APP_KEY, ADZUNA_COUNTRY,
            SEARCH_KEYWORDS, SEARCH_LOCATIONS, RESULTS_PER_PAGE, NUM_PAGES,
        )
        if not jobs:
            print("[Info] No live jobs fetched — using demo data instead.")
            jobs = DEMO_JOBS
    else:
        print("[Info] No Adzuna credentials — using demo data instead.")
        jobs = DEMO_JOBS

    # 2. Rank
    ranked = rank_jobs_live(MY_RESUME, jobs, DESIRED_SALARY)

    # 3. Draft cover letters for top matches only
    drafts = {}
    if not ANTHROPIC_API_KEY:
        print("[Warning] No ANTHROPIC_API_KEY set — skipping cover letter drafts.")
    elif Anthropic is None:
        print("[Warning] 'anthropic' package not installed — skipping cover letter drafts.")
        print("          Install with: pip install anthropic --break-system-packages")
    else:
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        top_matches = [j for j in ranked if j.final_score >= FIT_THRESHOLD][:MAX_DRAFTS]
        print(f"Generating {len(top_matches)} cover letter draft(s)...")
        for job in top_matches:
            drafts[job.title + job.company] = generate_cover_letter(client, MY_RESUME, job)

    # 4. Write dated report
    today_str = datetime.now().strftime("%Y-%m-%d")
    out_path = f"shortlist_{today_str}.md"
    write_report(ranked, drafts, out_path)
    print(f"\nDone. Report written to: {out_path}")


# ---------------------------------------------------------------------------
# SCHEDULING — run this automatically every morning
# ---------------------------------------------------------------------------
#
# macOS/Linux (cron): run `crontab -e` and add a line like:
#   0 8 * * * cd /path/to/this/folder && /usr/bin/python3 job_matcher_daily.py
#   (runs daily at 8:00 AM)
#
# Windows: use Task Scheduler to run:
#   python C:\path\to\job_matcher_daily.py
#   on a daily trigger.
#
# Either way, this only ever writes a report file with drafts + links.
# It never submits anything on your behalf — you still open the report
# and click "Apply" yourself on each listing.