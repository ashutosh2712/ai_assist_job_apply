"""
Job Matcher — Demo Version
---------------------------
Ranks demo job postings against a demo resume using:
  1. Keyword/skill overlap scoring (resume vs JD)
  2. Salary fit scoring (desired salary vs posted range)
  3. Combined weighted ranking

This uses hardcoded demo data. Once validated, swap `DEMO_RESUME` and
`DEMO_JOBS` for real resume text and live job feed data (Adzuna/Jooble/etc).
"""

import re
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# 1. DEMO DATA 
# ---------------------------------------------------------------------------

DEMO_RESUME = """
I am a passionate Full Stack Developer experienced in building scalable,
production-ready applications across frontend, backend, cloud, and microservices. 
I enjoy solving complex engineering problems, learning new technologies, and turning ideas into reliable products.
"""

DEMO_JOBS = [
    {
        "title": "Senior Full Stack engineer",
        "company": "Intel pvt ltd",
        "description": """
            Looking for a Full stack developer with strong SQL, Python,
            skills. Must have experience with AWS lambda, 
            Bonus: Airflow, A/B testing exposure.
        """,
        "salary_min": 1400000,
        "salary_max": 1900000,  # INR per annum
    },
    {
        "title": "Business Intelligence Engineer",
        "company": "RetailWorks",
        "description": """
            BI Engineer needed with Power BI, SQL, and Excel expertise.
            Should be able to build dashboards and work with stakeholders
            across departments. Snowflake experience is a plus.
        """,
        "salary_min": 1000000,
        "salary_max": 1300000,
    },
    {
        "title": "Machine Learning Engineer",
        "company": "NeuralStack AI",
        "description": """
            ML Engineer with strong Python, PyTorch, and deep learning
            experience. Must have deployed models in production. NLP
            experience preferred.
        """,
        "salary_min": 2000000,
        "salary_max": 2800000,
    },
    {
        "title": "Analytics Manager",
        "company": "HealthMetrics Inc",
        "description": """
            Manage a team of analysts. Require expertise in SQL, Python,
            statistical modeling, and stakeholder reporting. AWS and
            Airflow experience strongly preferred. Leadership experience
            required.
        """,
        "salary_min": None,  # simulates "not disclosed"
        "salary_max": None,
    },
]

DESIRED_SALARY = 2800000  # INR per annum — change this to your target

# Weighting between resume-fit and salary-fit in the final score
RESUME_WEIGHT = 0.6
SALARY_WEIGHT = 0.4


# ---------------------------------------------------------------------------
# 2. SKILL EXTRACTION 
# ---------------------------------------------------------------------------

# A basic skills vocabulary. In the real version this could be a much larger
# curated list, or dynamically extracted via an LLM.
SKILLS_VOCAB = [
    # Languages
    "python", "javascript", "typescript", "c++", "java", "scala", "c#",
    # Frontend
    "html", "css", "tailwind", "react", "reactjs", "react.js", "next.js",
    "nextjs", "three.js", "threejs", "gsap", "redux", "zustand",
    "backbone.js", "backbone", "bootstrap",
    # Backend
    "django", "fastapi", "flask", "node.js", "nodejs", "express",
    "rest api", "restful", "graphql", "grpc", "low level design", "lld",
    "system design", "microservices",
    # Databases
    "postgresql", "postgres", "mysql", "sql server", "mongodb", "sqlite",
    "sqlalchemy", "pgpool",
    # Cloud / DevOps
    "aws", "gcp", "azure", "docker", "kubernetes", "git", "bitbucket",
    "linux", "aws lambda", "cdk", "route 53", "cloud sql", "ci/cd",
    # Messaging / Search / Monitoring
    "kafka", "elasticsearch", "kibana", "elk",
    # Third-party integrations
    "openai", "stripe", "twilio", "anthrophic"
    # Practices
    "rbac", "data structures", "algorithms", "problem solving",
    "unit testing", "code review", "agile", "scrum",
]

def extract_skills(text: str) -> set:
    """Extract known skills mentioned in a block of text (case-insensitive)."""
    text_lower = text.lower()
    found = set()
    for skill in SKILLS_VOCAB:
        # word-boundary-ish match so 'sql' doesn't match inside another word
        pattern = r"(?<![a-z0-9])" + re.escape(skill) + r"(?![a-z0-9])"
        if re.search(pattern, text_lower):
            found.add(skill)

    return found


# ---------------------------------------------------------------------------
# 3. SCORING FUNCTIONS
# ---------------------------------------------------------------------------

def resume_fit_score(resume_skills: set, jd_skills: set) -> float:
    """
    Overlap-based fit score (0-10).
    Based on: what fraction of the JD's required skills does the resume cover?
    """
    if not jd_skills:
        return 5.0  # neutral score if JD has no extractable skills
    overlap = resume_skills.intersection(jd_skills)
    coverage = len(overlap) / len(jd_skills)
    return round(coverage * 10, 1)


def salary_fit_score(desired: int, salary_min, salary_max) -> tuple:
    """
    Salary fit score (0-10) + a flag string.
    - If no salary posted: neutral score (5.0), flagged for manual check.
    - If desired salary falls within range: high score.
    - If range is below desired: score drops based on the gap.
    - If range is above desired: still a good score (upside is fine).
    """
    if salary_min is None or salary_max is None:
        return 5.0, "Not disclosed — verify manually"

    if salary_min <= desired <= salary_max:
        return 10.0, "Within range"

    if desired < salary_min:
        # Job pays more than you asked — good news, still high score
        return 9.0, "Above your target (good)"

    # desired > salary_max -> job pays less than desired
    gap_ratio = (desired - salary_max) / desired
    score = max(0.0, round((1 - gap_ratio) * 10, 1))
    return score, f"Below target by ~{gap_ratio*100:.0f}%"


# ---------------------------------------------------------------------------
# 4. MAIN RANKING LOGIC
# ---------------------------------------------------------------------------

@dataclass
class RankedJob:
    title: str
    company: str
    resume_score: float
    salary_score: float
    salary_note: str
    final_score: float
    matched_skills: set = field(default_factory=set)
    missing_skills: set = field(default_factory=set)


def rank_jobs(resume_text: str, jobs: list, desired_salary: int) -> list:
    resume_skills = extract_skills(resume_text)
    ranked = []

    for job in jobs:
        jd_skills = extract_skills(job["description"])
        r_score = resume_fit_score(resume_skills, jd_skills)
        s_score, s_note = salary_fit_score(
            desired_salary, job["salary_min"], job["salary_max"]
        )
        final = round(RESUME_WEIGHT * r_score + SALARY_WEIGHT * s_score, 1)

        ranked.append(RankedJob(
            title=job["title"],
            company=job["company"],
            resume_score=r_score,
            salary_score=s_score,
            salary_note=s_note,
            final_score=final,
            matched_skills=resume_skills.intersection(jd_skills),
            missing_skills=jd_skills - resume_skills,
        ))

    ranked.sort(key=lambda j: j.final_score, reverse=True)
    return ranked


# ---------------------------------------------------------------------------
# 5. DISPLAY
# ---------------------------------------------------------------------------

def print_report(ranked_jobs: list):
    print("=" * 78)
    print("JOB MATCH REPORT (Demo Data — Keyword/Skill Overlap)")
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
    print("\n" + "=" * 78)


if __name__ == "__main__":
    results = rank_jobs(DEMO_RESUME, DEMO_JOBS, DESIRED_SALARY)
    print_report(results)