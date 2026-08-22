# PRD — Trade Me → Dice Automation

## Problem statement
Refactor an existing (already-manually-tested) Python Playwright automation that
transfers a Trade Me vehicle listing into the Dice classifieds portal. Turn it
into a maintainable, modular app with a simple web UI, WITHOUT breaking any
tested selectors/logic and WITHOUT ever auto-submitting the Dice ad.

## Users
- Single operator who posts Trade Me vehicles to Dice and reviews each ad
  manually before submitting.

## Core requirements (static)
- Preserve all tested selectors and extraction/fill logic verbatim.
- Never click the final Post/Submit button (stop for manual review).
- Preserve KM/engine source formatting; never swap km ↔ cc.
- Missing normal fields → `.`; price never `.`; missing ratings stay `- None -`.
- Ratings from `div.tm-listing-rating-star__blue[aria-label]` (exact numeric).
- First 5 real gallery photos only (`img.tm-gallery-view__thumbnail` → `/photoserver/full/`);
  `temp_photos/` cleared each job and git-ignored.
- Credentials from env only; never logged/committed.
- HEADED flag: headless in server/container, visible browser on user's machine.
- Simple web UI: paste URL → Start → live progress, data, ratings, photos, Dice fill.

## Architecture
- `backend/` FastAPI (`/api/health|start|status|close`) runs Playwright (sync) in a
  background thread; emits phase/data/ratings/photos/status/log events; single active job.
- `backend/automation/` package: config, models, utils, trade_me, photos, dice, runner.
- `frontend/` React console polling `/api/status` every 1s.
- `main.py` CLI preserves original interactive flow (ends at `page.pause()`).

## Implemented (2026-06)
- Non-destructive refactor of the original 1089-line `main.py` into modules
  (logic moved verbatim; only `print→log`, `headless=not HEADED`, per-photo
  download try/except added).
- FastAPI backend + React web UI with live log streaming, extracted-data grid,
  ratings, photo grid, phase stepper (Dice step shows "Skipped" when no creds).
- Credentials scrubbed from `test.py` / `upload_test.py` → env vars.
- `.env.example`, `.gitignore` (ignores `.env`, `temp_photos/`, `auth.json`).
- Verified end-to-end on sample listing 6051385299: km `39,000 km`, engine
  `2,996 cc` (preserved, not swapped), ratings 1.5/5/1.5/5, 5 photos, 2118-char
  description; Dice skipped gracefully without creds. Testing agent: 100% pass
  (20 backend tests + full UI run).

## Known / deferred
- `year` may derive from a body-text "Year" label rather than the title year
  (e.g. 2021 vs title 2022). PRESERVED original logic — awaiting user confirmation.
- KM/engine filled into Dice WITH unit (e.g. `55,830 km`) per existing tested
  code; spec example shows no unit — awaiting user confirmation before changing.
- Dice login/fill path not executable here (no creds) — user validates locally.

## Backlog (P1/P2)
- P2: In-memory job store eviction/TTL.
- P2: Per-job temp photo subdir (only matters if concurrency guard removed).
- P2: Surface tracebacks to logs on extraction failure for easier DOM-change diagnosis.
