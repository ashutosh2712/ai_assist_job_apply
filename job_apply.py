"""
Job Matcher — Live Version (Adzuna API)
-----------------------------------------
Fetches REAL job listings from the Adzuna API and ranks them against your
resume using the same keyword/skill-overlap + salary-fit scoring logic
from job_matcher_demo.py.

SETUP:
  1. Get free API credentials at https://developer.adzuna.com/
  2. Fill in ADZUNA_APP_ID and ADZUNA_APP_KEY below
  3. Install the requests library:  pip install requests --break-system-packages
  4. Edit SEARCH_KEYWORDS, SEARCH_LOCATION, and DESIRED_SALARY to match you
  5. Paste your real resume text into MY_RESUME

If credentials are missing, this script automatically falls back to the
demo data from job_matcher_demo.py so you can still see it working.

NOTE ON "APPLYING": Adzuna (like LinkedIn/Indeed/Naukri) does not offer an
API to submit applications. This script gets you a ranked shortlist with
direct application links — you still click "Apply" yourself on each site.
That's intentional: it keeps you ToS-compliant and avoids the account-ban
risk that comes with auto-submitting applications.
"""
import os
from dotenv import load_dotenv
import re
import requests  

# from job_demo (
#     extract_skills,
#     resume_fit_score,
#     salary_fit_score,
#     RankedJob,
#     RESUME_WEIGHT,
#     SALARY_WEIGHT,
#     DEMO_JOBS,
#     print_report,
# )

from job_matcher_demo import extract_skills, resume_fit_score, salary_fit_score, RankedJob, RESUME_WEIGHT, SALARY_WEIGHT, DEMO_JOBS, print_report


# ---------------------------------------------------------------------------
# 1. CONFIG — fill these in
# ---------------------------------------------------------------------------

load_dotenv()  # reads the .env file in the current directory into the environment
 
ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID", "")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY", "")

ADZUNA_COUNTRY = "in"          # 'in' = India. Adzuna supports gb, us, in, au, etc.
SEARCH_KEYWORDS = "software engineer"
SEARCH_LOCATION = "bangalore"
RESULTS_PER_PAGE = 20
NUM_PAGES = 1                  # increase to fetch more listings

DESIRED_SALARY = 2800000       # INR per annum — set your target

MY_RESUME = """
    With 4+ years of professional experience, 
    my journey has taken me from building full-stack applications 
    at Intel to working on SaaS platforms, cloud infrastructure, 
    and scalable systems. Over the years, I’ve grown from developing 
    web applications to designing microservices, serverless architectures, 
    APIs, and cloud solutions, working across technologies like React, Python, 
    Scala, Node.js, AWS, GCP, and Docker. Today, I focus on solving complex 
    engineering problems and building scalable, reliable, production-ready systems.
"""  # resume in text


# ---------------------------------------------------------------------------
# 2. FETCH JOBS FROM ADZUNA
# ---------------------------------------------------------------------------

def fetch_adzuna_jobs(app_id, app_key, country, keywords, location,
                       results_per_page=20, num_pages=1):
    """
    Calls the Adzuna Job Search API and returns a list of job dicts in the
    same shape used by job_matcher_demo.py: title, company, description,
    salary_min, salary_max, and (new) a real 'url' to apply.
    """

    all_jobs = []

    for page in range(1, num_pages + 1):
        url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"
        params = {
            "app_id": app_id,
            "app_key": app_key,
            "results_per_page": results_per_page,
            "what": keywords,
            "where": location,
            "content-type": "application/json",
        }

        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"[Warning] Adzuna API request failed: {e}")
            return []

        data = resp.json()
        for item in data.get("results", []):
            all_jobs.append({
                "title": item.get("title", "Untitled role"),
                "company": item.get("company", {}).get("display_name", "Unknown"),
                "description": item.get("description", ""),
                "salary_min": item.get("salary_min"),
                "salary_max": item.get("salary_max"),
                "url": item.get("redirect_url", ""),
            })

    return all_jobs


# ---------------------------------------------------------------------------
# 3. RANKING (same logic as demo, but carries the real application URL)
# ---------------------------------------------------------------------------

def rank_jobs_live(resume_text, jobs, desired_salary):
    resume_skills = extract_skills(resume_text)
    ranked = []

    for job in jobs:
        jd_skills = extract_skills(job["description"])
        r_score = resume_fit_score(resume_skills, jd_skills)
        s_score, s_note = salary_fit_score(
            desired_salary, job.get("salary_min"), job.get("salary_max")
        )
        final = round(RESUME_WEIGHT * r_score + SALARY_WEIGHT * s_score, 1)

        ranked_job = RankedJob(
            title=job["title"],
            company=job["company"],
            resume_score=r_score,
            salary_score=s_score,
            salary_note=s_note,
            final_score=final,
            matched_skills=resume_skills.intersection(jd_skills),
            missing_skills=jd_skills - resume_skills,
        )
        # attach URL dynamically (RankedJob dataclass doesn't define it,
        # but Python allows attaching extra attributes to instances)
        ranked_job.url = job.get("url", "")
        ranked.append(ranked_job)

    ranked.sort(key=lambda j: j.final_score, reverse=True)
    return ranked


def print_report_with_links(ranked_jobs):
    print("=" * 78)
    print("JOB MATCH REPORT (Live Adzuna Data)")
    print("=" * 78)
    for i, job in enumerate(ranked_jobs, 1):
        print(f"\n#{i}  {job.title} — {job.company}")
        print(f"    Final Score:   {job.final_score}/10")
        print(f"    Resume Fit:    {job.resume_score}/10")
        print(f"    Salary Fit:    {job.salary_score}/10  ({job.salary_note})")
        if job.matched_skills:
            print(f"    Matched skills:  {', '.join(sorted(job.matched_skills))}")
        if job.missing_skills:
            print(f"    Missing skills:  {', '.join(sorted(job.missing_skills))}")
        url = getattr(job, "url", "")
        if url:
            print(f"    Apply here:      {url}")
    print("\n" + "=" * 78)


# ---------------------------------------------------------------------------
# 4. MAIN
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
        print("[Info] No Adzuna credentials found — falling back to demo data.")
        print("       Get free credentials at https://developer.adzuna.com/\n")
        results = rank_jobs_live(MY_RESUME, DEMO_JOBS, DESIRED_SALARY)
    else:
        live_jobs = fetch_adzuna_jobs(
            ADZUNA_APP_ID, ADZUNA_APP_KEY, ADZUNA_COUNTRY,
            SEARCH_KEYWORDS, SEARCH_LOCATION,
            RESULTS_PER_PAGE, NUM_PAGES,
        )
        if not live_jobs:
            print("[Info] No live jobs fetched — falling back to demo data.\n")
            live_jobs = DEMO_JOBS
        results = rank_jobs_live(MY_RESUME, live_jobs, DESIRED_SALARY)

    print_report_with_links(results)