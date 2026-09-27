#!/bin/bash
# run_daily.sh — wrapper for cron to run the bulk apply-prep pipeline.
#
# Cron runs with a minimal environment (no PATH, no shell profile loaded),
# so this script pins the working directory and uses an explicit python3
# path to avoid "command not found" or "module not found" failures that
# only show up when run via cron and not when run by hand in a terminal.
#
# IMPORTANT (macOS): /usr/bin/python3 is Apple's built-in Python, which is
# almost certainly NOT the one your `pip install` used. Find the right one
# by running `which python3` in a normal Terminal window, then replace the
# PYTHON_BIN value below with that exact path.
 
PYTHON_BIN="/Library/Frameworks/Python.framework/Versions/3.13/bin/python3"   # <-- replace with the output of `which python3` on your machine
 
# Move into this script's own directory, wherever it's checked out
cd "$(dirname "$0")" || exit 1
 
# Log every run with a timestamp, appending so history isn't lost
echo "===== Run started: $(date) =====" >> cron.log
 
"$PYTHON_BIN" job_apply_bulk.py >> cron.log 2>&1
 
echo "===== Run finished: $(date) =====" >> cron.log
echo "" >> cron.log
 