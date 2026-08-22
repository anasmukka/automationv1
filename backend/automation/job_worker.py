"""Subprocess worker that runs one automation job.

Run as:  python -u -m automation.job_worker "<trade_me_url>"

Why a subprocess (not a thread)? Playwright's sync API launches its browser via
an asyncio subprocess, and asyncio cannot create subprocesses from a background
thread on Windows (raises NotImplementedError). Running the job in its own
process means Playwright executes on the process's MAIN thread — the standard,
cross-platform supported usage.

Output protocol (one item per line on stdout):
  * Structured events are prefixed with EVENT_PREFIX + JSON.
  * Everything else is a plain log line.
Input protocol (stdin):
  * A line equal to CLOSE_TOKEN ends the manual-review wait (closes the browser).
"""

import json
import sys
import threading

from automation.runner import run_job

EVENT_PREFIX = "@@EVT@@"
CLOSE_TOKEN = "@@CLOSE@@"


def main():
    if len(sys.argv) < 2:
        sys.stderr.write("usage: python -m automation.job_worker <url>\n")
        sys.exit(2)

    url = sys.argv[1]
    close_event = threading.Event()

    def emit(event):
        sys.stdout.write(EVENT_PREFIX + json.dumps(event) + "\n")
        sys.stdout.flush()

    def watch_stdin():
        try:
            for line in sys.stdin:
                if line.strip() == CLOSE_TOKEN:
                    close_event.set()
                    break
        except Exception:
            pass

    threading.Thread(target=watch_stdin, daemon=True).start()

    run_job(url, emit, close_event)


if __name__ == "__main__":
    main()
