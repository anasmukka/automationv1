# Trade Me → Dice Automation

Transfers a Trade Me vehicle listing into the Dice classifieds portal using
Playwright. It fills everything and then **stops for manual review — it never
clicks the final Post/Submit button.**

Two ways to run:
- **Web UI** — paste a URL, click Start, watch live progress (this repo's
  `backend/` + `frontend/`).
- **CLI** — `python main.py` (the original interactive flow, ends at
  `page.pause()` for review).

## Project structure
```
backend/
  server.py              FastAPI: /api/health /api/start /api/status /api/close
  automation/
    config.py            selectors, DICE_URL, HEADED flag, temp dir
    models.py            Listing dataclass
    utils.py             clean_number, fill_if_available, log()
    trade_me.py          vehicle info + star ratings (aria-label)
    photos.py            first-5 gallery extract + download
    dice.py              login / categories / fill / ratings / desc / upload / options
    runner.py            orchestrator (never submits)
  requirements.txt
frontend/                React web console
main.py                  CLI entry point
ratings_test.py photos_test.py upload_test.py test.py   standalone testers
.env.example  .gitignore  temp_photos/
```

## Setup (local, with a visible browser)
```bash
cd backend
pip install -r requirements.txt
python -m playwright install chromium

cp ../.env.example .env        # then edit backend/.env
#   DICE_USERNAME=...           (never committed — .env is git-ignored)
#   DICE_PASSWORD=...
#   HEADED=true                 (opens a visible browser on your machine)
```

### Run the CLI
```bash
cd ..
python main.py
```

### Run the web UI
```bash
# terminal 1
cd backend && uvicorn server:app --reload --port 8001
# terminal 2
cd frontend && yarn install && yarn start
```
Set `frontend/.env` → `REACT_APP_BACKEND_URL=http://localhost:8001` for local use.

## Safety & rules preserved
- Never clicks Post/Submit — stops at "Ready for review".
- KM/engine source formatting preserved (e.g. `55,830 km`, `1,298 cc`); never swapped.
- Missing normal fields → `.`; **price never** gets `.`; missing ratings stay `- None -`.
- Only the first 5 real gallery photos (`img.tm-gallery-view__thumbnail` → `/photoserver/full/`).
- `temp_photos/` cleared each job; git-ignored.
- Credentials from env only; never logged, never committed.
