"""
Mark Applied — quick CLI tool to update your application tracker
--------------------------------------------------------------------
After you click "Apply" on a job from your bulk_apply report, run this
to log it as applied in applications_log.csv (created by job_matcher_bulk.py).

USAGE:
  python3 mark_applied.py "<search text>" ["<optional note>"]

The search text matches against Title and Company (case-insensitive,
partial match is fine). If multiple rows match, it lists them so you can
narrow your search instead of guessing which one gets updated.

EXAMPLES:
  python3 mark_applied.py "Senior Software Engineer" "ABB"
  python3 mark_applied.py "FinEdge" "Referred by a friend"
"""

import sys
import csv
from datetime import datetime

LOG_PATH = "applications_log.csv"


def load_rows(filepath):
    with open(filepath, "r", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader), reader.fieldnames


def save_rows(filepath, rows, fieldnames):
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    if len(sys.argv) < 2:
        print('Usage: python3 mark_applied.py "<search text>" ["<optional note>"]')
        sys.exit(1)

    search_text = sys.argv[1].lower()
    note = sys.argv[2] if len(sys.argv) > 2 else ""

    try:
        rows, fieldnames = load_rows(LOG_PATH)
    except FileNotFoundError:
        print(f"[Error] {LOG_PATH} not found. Run job_matcher_bulk.py first "
              f"to generate your tracker.")
        sys.exit(1)

    matches = [
        i for i, row in enumerate(rows)
        if search_text in row["Title"].lower() or search_text in row["Company"].lower()
    ]

    if not matches:
        print(f'No entries matched "{sys.argv[1]}". Check applications_log.csv for exact wording.')
        sys.exit(1)

    if len(matches) > 1:
        # Prefer rows still marked 'Not Applied' if there's ambiguity
        pending = [i for i in matches if rows[i]["Status"] == "Not Applied"]
        candidates = pending if pending else matches
        if len(candidates) > 1:
            print(f'Multiple matches for "{sys.argv[1]}" — be more specific:\n')
            for i in candidates:
                r = rows[i]
                print(f"  - {r['Title']} — {r['Company']}  (Status: {r['Status']})")
            sys.exit(1)
        matches = candidates

    idx = matches[0]
    rows[idx]["Status"] = "Applied"
    rows[idx]["Date Applied"] = datetime.now().strftime("%Y-%m-%d")
    if note:
        rows[idx]["Notes"] = note

    save_rows(LOG_PATH, rows, fieldnames)
    print(f"Marked as applied: {rows[idx]['Title']} — {rows[idx]['Company']}")


if __name__ == "__main__":
    main()