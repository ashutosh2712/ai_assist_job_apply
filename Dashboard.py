"""
Application Tracker Dashboard
----------------------------------
A tiny local web dashboard for applications_log.csv. Instead of typing
search text into mark_applied.py, you get a page with a "Mark Applied"
button next to each pending job — one click updates the CSV instantly.

This only ever reads/writes YOUR OWN local CSV file. It does not interact
with LinkedIn, Naukri, Indeed, or any company site in any way — that
distinction matters, since it keeps this tool entirely within your own
data rather than automating anything on the job platforms themselves.

SETUP:
  pip install flask --break-system-packages

RUN:
  python3 dashboard.py
  Then open http://127.0.0.1:5000 in your browser.
"""

import csv
import os
from datetime import datetime

from flask import Flask, request, redirect, url_for

LOG_PATH = "applications_log.csv"
app = Flask(__name__)


def load_rows():
    if not os.path.exists(LOG_PATH):
        return [], []
    with open(LOG_PATH, "r", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader), reader.fieldnames


def save_rows(rows, fieldnames):
    with open(LOG_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


PAGE_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <title>Application Tracker</title>
  <style>
    body {{ font-family: -apple-system, sans-serif; max-width: 900px; margin: 40px auto; padding: 0 20px; color: #222; }}
    h1 {{ font-size: 22px; }}
    .stats {{ color: #666; margin-bottom: 20px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ text-align: left; padding: 10px 8px; border-bottom: 1px solid #eee; font-size: 14px; vertical-align: top; }}
    th {{ color: #888; font-weight: 600; font-size: 12px; text-transform: uppercase; }}
    .applied {{ color: #1a7f37; font-weight: 600; }}
    .pending {{ color: #b45309; font-weight: 600; }}
    a {{ color: #2563eb; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    button {{ background: #16a34a; color: white; border: none; padding: 6px 14px; border-radius: 6px; cursor: pointer; font-size: 13px; }}
    button:hover {{ background: #15803d; }}
    tr:hover {{ background: #fafafa; }}
  </style>
</head>
<body>
  <h1>📋 Application Tracker</h1>
  <div class="stats">{applied_count} applied &middot; {pending_count} pending &middot; {total_count} total</div>
  <table>
    <tr><th>Title</th><th>Company</th><th>Salary</th><th>Status</th><th>Link</th><th></th></tr>
    {rows_html}
  </table>
</body>
</html>
"""

ROW_TEMPLATE = """
<tr>
  <td>{title}</td>
  <td>{company}</td>
  <td>{salary_note}</td>
  <td class="{status_class}">{status}{date_applied}</td>
  <td>{link}</td>
  <td>{action}</td>
</tr>
"""


@app.route("/")
def dashboard():
    rows, _ = load_rows()
    if not rows:
        return "<p style='font-family:sans-serif;margin:40px;'>No jobs tracked yet. Run job_matcher_bulk.py first.</p>"

    applied_count = sum(1 for r in rows if r["Status"] == "Applied")
    pending_count = len(rows) - applied_count

    rows_html = ""
    for i, row in enumerate(rows):
        is_applied = row["Status"] == "Applied"
        status_class = "applied" if is_applied else "pending"
        date_applied = f" ({row['Date Applied']})" if row.get("Date Applied") else ""
        link = f'<a href="{row["URL"]}" target="_blank">Open ↗</a>' if row.get("URL") else "—"
        action = "" if is_applied else (
            f'<form method="POST" action="/mark/{i}" style="margin:0;">'
            f'<button type="submit">Mark Applied</button></form>'
        )
        rows_html += ROW_TEMPLATE.format(
            title=row["Title"], company=row["Company"], salary_note=row["Salary Note"],
            status_class=status_class, status=row["Status"], date_applied=date_applied,
            link=link, action=action,
        )

    return PAGE_TEMPLATE.format(
        applied_count=applied_count, pending_count=pending_count,
        total_count=len(rows), rows_html=rows_html,
    )


@app.route("/mark/<int:index>", methods=["POST"])
def mark_applied(index):
    rows, fieldnames = load_rows()
    if 0 <= index < len(rows):
        rows[index]["Status"] = "Applied"
        rows[index]["Date Applied"] = datetime.now().strftime("%Y-%m-%d")
        save_rows(rows, fieldnames)
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    print("Dashboard running at http://127.0.0.1:5000")
    app.run(debug=False, port=5000)