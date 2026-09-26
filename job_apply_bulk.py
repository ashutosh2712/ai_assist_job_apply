"""
Job Matcher — Bulk Apply-Prep Version
-----------------------------------------
No ranking. Just: does this job clear your salary floor and experience
fit? If yes, draft a cover letter and add it to today's list. The goal
is maximum volume of ready-to-click applications, not a top-5 shortlist.

Filters (pass/fail, not scored):
  1. SALARY  — job's range must reach your minimum, OR salary is
               undisclosed (included but flagged "verify manually")
  2. EXPERIENCE — JD's stated years requirement must not clearly exceed
               your experience + a small buffer. No mention -> included.

Everything that passes both filters gets a drafted cover letter via the
Claude API. You still click "Apply" yourself on each one 

SETUP: same as job_daily_apply.py
  .env needs: ADZUNA_APP_ID, ADZUNA_APP_KEY, ANTHROPIC_API_KEY
"""

import os
import re
import csv
from datetime import datetime
from urllib.parse import urlparse

import requests
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
    MY_RESUME,
    fetch_adzuna_jobs_multi,
)
from job_matcher_demo import DEMO_JOBS, extract_skills


load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = "claude-sonnet-5"  # check docs.claude.com for current model names

# --- Your filter criteria ---
MIN_ACCEPTABLE_SALARY = 1500000   # INR per annum — your floor, from ₹15L–25L range
MY_YEARS_EXPERIENCE = 4.5        # midpoint of your 2-5 years — set your exact number
EXPERIENCE_BUFFER = 5           # how many extra years of "required" you'll still consider

# Optional: exclude/include specific companies. Leave empty to skip.
COMPANY_BLOCKLIST = []   # e.g. ["Some Company Name"]
COMPANY_ALLOWLIST = []   # if non-empty, ONLY these companies are kept

# Safety cap on API spend — raise if you want more drafts per run
MAX_DRAFTS = 1

# Where the application tracking log lives — same folder as this script
APPLICATIONS_LOG_PATH = "applications_log.csv"
LOG_COLUMNS = [
    "Date Found", "Title", "Company", "Salary Note", "Experience Note",
    "Applies Via", "URL", "Status", "Date Applied", "Notes",
]


# ---------------------------------------------------------------------------
# FILTER 1: SALARY
# ---------------------------------------------------------------------------

def passes_salary_filter(job, min_salary):
    """Returns (passes: bool, note: str)."""
    s_min = job.get("salary_min")
    s_max = job.get("salary_max")

    if s_min is None and s_max is None:
        return True, "Not disclosed — verify manually"

    top_of_range = s_max if s_max is not None else s_min
    if top_of_range >= min_salary:
        return True, "Meets your floor"

    return False, f"Below your floor (max offered ~₹{top_of_range:,.0f})"


# ---------------------------------------------------------------------------
# FILTER 2: EXPERIENCE
# ---------------------------------------------------------------------------

EXPERIENCE_PATTERNS = [
    r"(\d+)\s*\+\s*years",
    r"(\d+)\s*-\s*\d+\s*years",
    r"minimum\s*(?:of\s*)?(\d+)\s*years",
    r"at least\s*(\d+)\s*years",
    r"(\d+)\s*to\s*\d+\s*years",
]


def extract_required_years(text: str):
    """Returns the highest 'years required' figure found, or None if none found."""
    text_lower = text.lower()
    found = []
    for pattern in EXPERIENCE_PATTERNS:
        for match in re.finditer(pattern, text_lower):
            found.append(int(match.group(1)))
    return max(found) if found else None


def passes_experience_filter(job_description, my_years, buffer):
    required = extract_required_years(job_description)
    if required is None:
        return True, "No experience requirement stated"
    if required <= my_years + buffer:
        return True, f"Requires ~{required}+ yrs — within reach"
    return False, f"Requires ~{required}+ yrs — likely above your experience"


# ---------------------------------------------------------------------------
# FILTER 3: COMPANY (optional)
# ---------------------------------------------------------------------------

def passes_company_filter(company: str):
    if COMPANY_ALLOWLIST and company not in COMPANY_ALLOWLIST:
        return False
    if company in COMPANY_BLOCKLIST:
        return False
    return True


# ---------------------------------------------------------------------------
# DESTINATION RESOLVER — reveal where an "apply" link actually leads
# ---------------------------------------------------------------------------

# Recognize common application systems by domain fragment, purely for a
# friendlier label in the report (e.g. "Greenhouse" instead of a raw domain).
KNOWN_ATS_DOMAINS = {
    "greenhouse.io": "Greenhouse",
    "lever.co": "Lever",
    "myworkdayjobs.com": "Workday",
    "icims.com": "iCIMS",
    "smartrecruiters.com": "SmartRecruiters",
    "taleo.net": "Taleo",
    "successfactors.com": "SuccessFactors",
    "naukri.com": "Naukri",
    "linkedin.com": "LinkedIn",
    "indeed.com": "Indeed",
}


def resolve_destination(url: str, timeout: int = 8):
    """
    Follows redirects (e.g. Adzuna's tracking link) to find the real
    destination and label it if it matches a known application system.
    Returns (final_url, domain, label). On any failure, returns the
    original url with domain/label as 'Unknown' so the report still works.
    """
    if not url:
        return url, "Unknown", "Unknown"

    try:
        resp = requests.head(url, allow_redirects=True, timeout=timeout)
        final_url = resp.url
    except requests.exceptions.RequestException:
        try:
            # Some servers reject HEAD; fall back to a lightweight GET
            resp = requests.get(url, allow_redirects=True, timeout=timeout, stream=True)
            final_url = resp.url
            resp.close()
        except requests.exceptions.RequestException:
            return url, "Unknown", "Unknown"

    domain = urlparse(final_url).netloc.replace("www.", "")
    label = next((v for k, v in KNOWN_ATS_DOMAINS.items() if k in domain), domain)
    return final_url, domain, label


# ---------------------------------------------------------------------------
# APPLICATION TRACKING LOG (CSV)
# ---------------------------------------------------------------------------

def log_to_csv(passed_jobs, filepath=APPLICATIONS_LOG_PATH):
    """
    Appends newly-found jobs to a persistent CSV tracker. Skips jobs whose
    URL is already logged, so re-running the script daily doesn't create
    duplicate rows. New rows start with Status='Not Applied' — you (or
    mark_applied.py) update that once you've actually applied.
    """
    existing_keys = set()
    file_exists = os.path.exists(filepath)

    if file_exists:
        with open(filepath, "r", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = row.get("URL") or f"{row.get('Title','')}|{row.get('Company','')}"
                existing_keys.add(key)

    new_rows = []
    today = datetime.now().strftime("%Y-%m-%d")
    for item in passed_jobs:
        dedupe_key = item["url"] or f"{item['title']}|{item['company']}"
        if dedupe_key in existing_keys:
            continue  # already logged from a previous run
        new_rows.append({
            "Date Found": today,
            "Title": item["title"],
            "Company": item["company"],
            "Salary Note": item["salary_note"],
            "Experience Note": item["experience_note"],
            "Applies Via": item.get("destination_label", "Unknown"),
            "URL": item["url"],
            "Status": "Not Applied",
            "Date Applied": "",
            "Notes": "",
        })

    if not new_rows:
        print("[Log] No new jobs to add — all already tracked.")
        return

    with open(filepath, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_COLUMNS)
        if not file_exists:
            writer.writeheader()
        writer.writerows(new_rows)

    print(f"[Log] Added {len(new_rows)} new job(s) to {filepath}")


# ---------------------------------------------------------------------------
# COVER LETTER DRAFTING (same approach as job_matcher_daily.py)
# ---------------------------------------------------------------------------

def generate_cover_letter(client, resume_text, title, company, matched_skills):
    prompt = f"""You are helping a job applicant draft a short cover letter.

RESUME:
{resume_text.strip()}

JOB TITLE: {title}
COMPANY: {company}
MATCHED SKILLS: {', '.join(sorted(matched_skills)) or 'none clearly listed'}

Write a concise, natural-sounding cover letter (150-200 words) tailored to
this role. Reference 2-3 concrete points of overlap between the resume and
the role. Avoid generic filler phrases. Do not invent experience not
present in the resume. End with a simple, confident closing line."""

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
# MAIN
# ---------------------------------------------------------------------------

def write_report(passed_jobs, filepath):
    lines = []
    lines.append(f"# Bulk Apply List — {datetime.now().strftime('%Y-%m-%d')}\n")
    lines.append(f"Filters: salary floor ₹{MIN_ACCEPTABLE_SALARY:,} | "
                 f"experience ~{MY_YEARS_EXPERIENCE} yrs (+{EXPERIENCE_BUFFER} buffer)\n")
    lines.append(f"**{len(passed_jobs)} jobs passed your filters.**\n")
    lines.append("---\n")

    for i, item in enumerate(passed_jobs, 1):
        lines.append(f"## {i}. {item['title']} — {item['company']}\n")
        lines.append(f"- **Salary:** {item['salary_note']}")
        lines.append(f"- **Experience fit:** {item['experience_note']}")
        if item["matched_skills"]:
            lines.append(f"- **Overlap with your resume:** {', '.join(sorted(item['matched_skills']))}")
        if item["url"]:
            lines.append(f"- **Applies via:** {item.get('destination_label', 'Unknown')}")
            lines.append(f"- **Apply here:** {item['url']}")
        if item["draft"]:
            lines.append("\n**Draft cover letter (review before using):**\n")
            lines.append("> " + item["draft"].replace("\n", "\n> "))
        lines.append("\n---\n")

    with open(filepath, "w") as f:
        f.write("\n".join(lines))


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

    resume_skills = extract_skills(MY_RESUME)

    # 2. Apply filters
    passed = []
    for job in jobs:
        company = job.get("company", "Unknown")
        if not passes_company_filter(company):
            continue

        sal_ok, sal_note = passes_salary_filter(job, MIN_ACCEPTABLE_SALARY)
        if not sal_ok:
            continue

        exp_ok, exp_note = passes_experience_filter(
            job.get("description", ""), MY_YEARS_EXPERIENCE, EXPERIENCE_BUFFER
        )
        if not exp_ok:
            continue

        jd_skills = extract_skills(job.get("description", ""))
        raw_url = job.get("url", "")
        final_url, domain, label = resolve_destination(raw_url)
        passed.append({
            "title": job.get("title", "Untitled role"),
            "company": company,
            "url": final_url,
            "destination_label": label,
            "salary_note": sal_note,
            "experience_note": exp_note,
            "matched_skills": resume_skills.intersection(jd_skills),
            "draft": None,
        })

    print(f"{len(passed)} of {len(jobs)} jobs passed your filters.")
    print("Resolving application destinations (this makes one request per job)...")

    # 3. Draft cover letters for everything that passed (up to MAX_DRAFTS)
    if not ANTHROPIC_API_KEY:
        print("[Warning] No ANTHROPIC_API_KEY set — skipping cover letter drafts.")
    elif Anthropic is None:
        print("[Warning] 'anthropic' package not installed — skipping drafts.")
    else:
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        to_draft = passed[:MAX_DRAFTS]
        print(f"Generating {len(to_draft)} cover letter draft(s)...")
        for item in to_draft:
            item["draft"] = generate_cover_letter(
                client, MY_RESUME, item["title"], item["company"], item["matched_skills"]
            )
        if len(passed) > MAX_DRAFTS:
            print(f"[Note] {len(passed) - MAX_DRAFTS} jobs passed filters but were "
                  f"skipped for drafting (MAX_DRAFTS={MAX_DRAFTS}). Raise the cap if needed.")

    # 4. Write report
    out_path = f"bulk_apply_{datetime.now().strftime('%Y-%m-%d')}.md"
    write_report(passed, out_path)
    print(f"\nDone. Report written to: {out_path}")

    # 5. Log to the persistent CSV tracker (skips duplicates automatically)
    log_to_csv(passed)