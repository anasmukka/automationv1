"""Backend API tests for the Trade Me -> Dice automation service.

Modules under test:
  * server.py            -> /api/health, /api/start, /api/status/{id}, /api/close/{id}
  * automation/job_worker.py -> subprocess worker event/log streaming
  * automation/runner.py -> job orchestration + graceful Dice skip
  * automation/trade_me.py, automation/photos.py -> resilient extraction assertions
"""

import os
import re
import time
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL is missing")
BASE_URL = base_url.rstrip("/")

SAMPLE_URL = "https://www.trademe.co.nz/a/motors/cars/jaguar/f-pace/listing/6051385299"
POLL_TIMEOUT = 150
TRADE_ME_SRC = Path("/app/backend/automation/trade_me.py")


@pytest.fixture(scope="session")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------------- health ----------------
class TestHealth:
    def test_health(self, api):
        r = api.get(f"{BASE_URL}/api/health", timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "ok"
        assert d["headed"] is False
        assert d["dice_configured"] is False
        assert isinstance(d["dice_url"], str) and d["dice_url"].startswith("http")


# ---------------- validation / errors ----------------
class TestValidation:
    def test_start_empty_url(self, api):
        r = api.post(f"{BASE_URL}/api/start", json={"url": ""}, timeout=30)
        assert r.status_code == 400, r.text
        assert "required" in r.json().get("detail", "").lower()

    def test_start_whitespace_url(self, api):
        r = api.post(f"{BASE_URL}/api/start", json={"url": "   "}, timeout=30)
        assert r.status_code == 400, r.text

    def test_start_missing_field(self, api):
        r = api.post(f"{BASE_URL}/api/start", json={}, timeout=30)
        assert r.status_code == 422, r.text

    def test_status_unknown_job(self, api):
        r = api.get(f"{BASE_URL}/api/status/does-not-exist", timeout=30)
        assert r.status_code == 404, r.text

    def test_close_unknown_job(self, api):
        r = api.post(f"{BASE_URL}/api/close/does-not-exist", timeout=30)
        assert r.status_code == 404, r.text


# ---------------- static code checks: resilient extraction rules ----------------
class TestExtractionRules:
    """Source-level checks of trade_me.py regex behaviour (no browser needed)."""

    @pytest.fixture(scope="class")
    def src(self):
        return TRADE_ME_SRC.read_text(encoding="utf-8")

    def test_star_rating_regex_handles_zero_and_halves(self, src):
        m = re.search(r'r"\(\[0-9\][^"]*out of[^"]*"', src)
        assert m, "star rating regex not found in extract_star_rating"
        pattern = m.group(0)[2:-1]  # strip r" and trailing "
        for aria, expected in [
            ("0 out of 6 stars", "0"),
            ("3.5 out of 6 stars", "3.5"),
            ("5 out of 5 stars", "5"),
            ("1.5 out of 6 stars", "1.5"),
        ]:
            got = re.search(pattern, aria, re.IGNORECASE)
            assert got, f"regex failed to match {aria!r}"
            assert got.group(1) == expected, f"{aria!r} -> {got.group(1)!r}"

    def test_rating_selector_is_blue_star_aria_label(self, src):
        assert "div.tm-listing-rating-star__blue[aria-label]" in src

    def test_body_type_includes_station_wagon(self, src):
        assert '"Station Wagon"' in src
        # Station Wagon must be checked before the generic "Wagon"
        assert src.index('"Station Wagon"') < src.index('"Wagon"')

    def test_km_engine_patterns_keep_unit_and_source_spacing(self, src):
        """Replicate the find_first patterns against no-modal badge text.

        Bug-fix #2: the value must now INCLUDE the unit and preserve source spacing.
        """
        km_pats = [
            r"odometer\s*[:\r\n]*\s*((?:\d{1,3}(?:,\d{3})+|\d{4,})\s*km)",
            r"(?<![\d/])((?:\d{1,3}(?:,\d{3})+|\d{4,})\s*km)\b",
        ]
        cc_pats = [
            r"engine\s*(?:size)?\s*[:\r\n]*\s*((?:\d{3,}(?:,\d{3})*|\d{1,3}(?:,\d{3})+)\s*cc)",
            r"(?<![\d/])((?:\d{3,}(?:,\d{3})*|\d{1,3}(?:,\d{3})+)\s*cc)\b",
        ]
        for pats in (km_pats, cc_pats):
            for p in pats:
                assert p in src, f"pattern drifted from source: {p}"

        def first(pats, text):
            for p in pats:
                m = re.search(p, text, re.IGNORECASE)
                if m:
                    return m.group(1).strip()
            return None

        badges = "262,000km\nStation Wagon\nPetrol\n4477cc\nManual"
        assert first(km_pats, badges) == "262,000km"
        assert first(cc_pats, badges) == "4477cc"

        badges2 = "39,000 km\n4,477cc\n9.2 L / 100km\n149 grams/km"
        assert first(km_pats, badges2) == "39,000 km"
        assert first(cc_pats, badges2) == "4,477cc"

        assert first(cc_pats, "Engine size\n2,996 cc") == "2,996 cc"

        # units never swapped: km pattern must not pick a cc value and vice versa
        assert first(km_pats, "4477cc") is None
        assert first(cc_pats, "262,000km") is None

    def test_number_plate_regex(self, src):
        """Refinement: LABEL is case-insensitive ((?i:...)), CAPTURE stays uppercase."""
        primary = r"(?i:number\s*plate)[\s:\r\n]+([A-Z0-9]{2,7})\b"
        fallback = r"(?i:\bplate\b)[\s:\r\n]+([A-Z0-9]{2,7})\b"
        assert primary in src, "primary number plate pattern drifted from source"
        assert fallback in src, "plate fallback pattern drifted from source"

        # primary alone must handle the real page label
        assert re.search(primary, "Number plate\nPNF703\nYear\n2022").group(1) == "PNF703"
        assert re.search(primary, "number plate: PNF703").group(1) == "PNF703"
        # lowercase label matches, but a lowercase capture must NOT
        assert re.search(primary, "number plate\nabc12") is None
        # Title-case following word must not be captured
        assert re.search(primary, "Number plate\nHistory") is None

        def extract(text):
            """Replicate the two-pattern source logic."""
            m = re.search(primary, text) or re.search(fallback, text)
            return m.group(1).strip().upper() if m else None

        assert extract("Number plate\nPNF703\nYear\n2022") == "PNF703"
        assert extract("number plate: PNF703") == "PNF703"
        assert extract("Number plate\nhistory") is None
        assert extract("Number plate history\nNo issues") is None

        # capture must remain case-sensitive (no global re.IGNORECASE flag)
        block = src[src.index("number_plate = None"):src.index("if number_plate:")]
        assert "IGNORECASE" not in block, "plate capture must stay case-sensitive"
        assert ".upper()" in block

    def test_dice_ratings_selection_is_robust(self):
        """Code-review checks on dice.py fill_dice_ratings (no creds -> cannot run live)."""
        dice_src = Path("/app/backend/automation/dice.py").read_text(encoding="utf-8")
        block = dice_src[dice_src.index("def fill_dice_ratings"):]
        block = block[: block.index("\ndef ", 10)] if "\ndef " in block[10:] else block
        assert "if value is None" in block and "[SKIP]" in block, "must skip None (leave '- None -')"
        assert 'wait_for(state="attached"' in block, "must wait for select to attach"
        assert '{"value": cand}, {"label": cand}' in block, "must try value then label"
        assert 'f"{int(f)}.0"' in block, "must try numeric variant '5.0'"
        assert 'dispatch_event("change")' in block, "must dispatch change event"
        assert "Could not select" in block and "Available options" in block, \
            "must log option dump on total failure"
        # NEW refinement: index-based option-text fallback before the error dump
        assert 'locator("option").all_inner_texts()' in block, "must read option inner texts"
        assert "select_option(index=idx)" in block, "must select by option index"
        assert "import re" in dice_src, "dice.py must import re for the text fallback"
        assert block.index("all_inner_texts") < block.index("Could not select"), \
            "option-text fallback must run BEFORE the error dump"

        # replicate the fallback matcher semantics
        def pick(value, options):
            for idx, txt in enumerate(options):
                t = (txt or "").strip()
                if t == value or re.match(rf"^{re.escape(value)}(\D|$)", t):
                    return idx
            return None

        assert pick("3.5", ["- None -", "3", "3.5", "4"]) == 2
        assert pick("3.5", ["- None -", "3 stars", "3.5 stars"]) == 2
        assert pick("3", ["- None -", "3 stars", "3.5 stars"]) == 1
        assert pick("5", ["- None -", "1", "2"]) is None
        # KNOWN LIMITATION (reported): (\D|$) treats "." as a boundary, so an
        # integer value can match a half-star label if it appears first.
        assert pick("3", ["- None -", "3.5 stars", "3 stars"]) == 1  # matches "3.5 stars"
        # config mapping
        cfg = Path("/app/backend/automation/config.py").read_text(encoding="utf-8")
        for field, sel in [("energy_rating", "#exf_41"), ("overall_safety", "#exf_42"),
                           ("carbon_rating", "#exf_43"), ("driver_safety", "#exf_44")]:
            assert f'"{field}": "{sel}"' in cfg, f"{field} -> {sel} mapping missing"

    def test_dice_form_fills_number_plate_as_is(self):
        dice_src = Path("/app/backend/automation/dice.py").read_text(encoding="utf-8")
        assert '"number_plate": listing.number_plate,' in dice_src
        cfg = Path("/app/backend/automation/config.py").read_text(encoding="utf-8")
        assert '"number_plate": "#exf_31"' in cfg

    def test_extraction_does_not_require_modal(self, src):
        """Visible body_text must be the first source passed to find_first."""
        block = src[src.index("kilometer = find_first"):src.index("if kilometer:")]
        assert block.index("body_text") < block.index("vehicle_details_text")


# ---------------- full extraction job ----------------
@pytest.fixture(scope="module")
def completed_job(api):
    r = api.post(f"{BASE_URL}/api/start", json={"url": SAMPLE_URL}, timeout=60)
    if r.status_code == 409:
        time.sleep(60)
        r = api.post(f"{BASE_URL}/api/start", json={"url": SAMPLE_URL}, timeout=60)
    assert r.status_code == 200, f"start failed: {r.status_code} {r.text}"
    job_id = r.json()["job_id"]
    assert isinstance(job_id, str) and job_id

    snap = None
    deadline = time.time() + POLL_TIMEOUT
    while time.time() < deadline:
        s = api.get(f"{BASE_URL}/api/status/{job_id}", timeout=30)
        assert s.status_code == 200, s.text
        snap = s.json()
        if snap.get("done"):
            break
        time.sleep(2)
    assert snap and snap.get("done"), f"job did not finish in {POLL_TIMEOUT}s: {snap and snap.get('phase')}"
    return snap


class TestJobFlow:
    def test_conflict_and_incremental_log_streaming(self, api):
        """Start a job, verify 409 on a second start, and that logs stream incrementally."""
        r = api.post(f"{BASE_URL}/api/start", json={"url": SAMPLE_URL}, timeout=60)
        assert r.status_code == 200, r.text
        job_id = r.json()["job_id"]
        r2 = api.post(f"{BASE_URL}/api/start", json={"url": SAMPLE_URL}, timeout=60)
        assert r2.status_code == 409, f"expected 409, got {r2.status_code} {r2.text}"

        counts = []
        statuses = []
        deadline = time.time() + POLL_TIMEOUT
        snap = None
        while time.time() < deadline:
            snap = api.get(f"{BASE_URL}/api/status/{job_id}", timeout=30).json()
            counts.append(len(snap["logs"]))
            statuses.append(snap["status"])
            if snap.get("done"):
                break
            time.sleep(1)
        assert snap and snap.get("done"), "first job never completed"

        distinct = sorted(set(counts))
        assert len(distinct) >= 3, f"logs did not stream incrementally: {counts}"
        assert counts == sorted(counts), f"log count decreased: {counts}"
        assert "running" in statuses and statuses[-1] == "completed", statuses

    def test_status_completed(self, completed_job):
        assert completed_job["status"] == "completed", completed_job.get("error") or completed_job.get("message")
        assert completed_job["done"] is True
        assert completed_job["error"] is None

    # ---- km / engine WITH units (bug-fix #2) ----
    def test_kilometer_includes_unit(self, completed_job):
        km = completed_job["listing"]["kilometer"]
        assert km == "39,000 km", f"expected '39,000 km', got {km!r}"

    def test_engine_includes_unit(self, completed_job):
        cc = completed_job["listing"]["engine_cc"]
        assert cc == "2,996 cc", f"expected '2,996 cc', got {cc!r}"

    def test_km_and_engine_not_swapped(self, completed_job):
        km_raw = completed_job["listing"]["kilometer"]
        cc_raw = completed_job["listing"]["engine_cc"]
        assert km_raw.lower().endswith("km") and cc_raw.lower().endswith("cc")
        km = int(re.sub(r"[^\d]", "", km_raw))
        cc = int(re.sub(r"[^\d]", "", cc_raw))
        assert km > cc, f"km/engine look swapped: km={km} cc={cc}"
        assert km >= 1000
        assert 100 <= cc <= 10000

    # ---- number plate (bug-fix #1) ----
    def test_number_plate_extracted(self, completed_job):
        plate = completed_job["listing"]["number_plate"]
        assert plate, "number_plate is empty"
        assert plate == "PNF703", f"expected 'PNF703', got {plate!r}"
        assert plate == plate.upper()
        assert plate != "."

    def test_number_plate_log(self, completed_job):
        logs = "\n".join(completed_job["logs"])
        assert "[TRADE ME] Number plate: PNF703" in logs, logs[-1200:]
        assert "[WARN] Could not find number plate" not in logs

    def test_ask_price_has_dollar(self, completed_job):
        assert completed_job["listing"]["ask_price"].startswith("$")

    def test_ratings(self, completed_job):
        ratings = completed_job["ratings"]
        assert isinstance(ratings, dict)
        assert [ratings.get("energy_rating"), ratings.get("overall_safety"),
                ratings.get("carbon_rating"), ratings.get("driver_safety")] == \
            ["1.5", "5", "1.5", "5"], ratings
        for key in ["energy_rating", "overall_safety", "carbon_rating", "driver_safety"]:
            val = ratings.get(key)
            assert re.fullmatch(r"[0-9]+(?:\.5)?", str(val)), f"rating {key} not numeric: {val!r}"

    # ---- NEW: resilient-extraction log lines ----
    def test_resilient_extraction_logs(self, completed_job):
        logs = "\n".join(completed_job["logs"])
        for expected in [
            "[TRADE ME] Reading vehicle badges...",
            "[TRADE ME] KM: 39,000 km",
            "[TRADE ME] Engine: 2,996 cc",
            "[TRADE ME] Fuel: Petrol",
            "[TRADE ME] Reading ratings...",
        ]:
            assert expected in logs, f"missing log line: {expected!r}"
        assert re.search(r"\[TRADE ME\] Body: \S+", logs), "missing Body log"
        assert re.search(r"\[TRADE ME\] Transmission: \S+", logs), "missing Transmission log"

    def test_per_rating_logs(self, completed_job):
        logs = "\n".join(completed_job["logs"])
        for name in ["Energy Economy", "Overall Safety", "Carbon Emissions", "Driver Safety"]:
            assert re.search(rf"\[RATING\] {re.escape(name)}: [0-9.]+", logs) or \
                f"[WARN] Could not find {name} rating" in logs, f"no [RATING]/[WARN] line for {name}"
        # for this listing all 4 ratings exist -> no rating WARNs
        assert "[WARN] Could not find" not in logs or "rating" not in logs.split("[WARN] Could not find")[-1][:40], logs[-800:]

    # ---- regressions ----
    def test_listing_fields(self, completed_job):
        listing = completed_job["listing"]
        assert isinstance(listing, dict)
        for key in ["title", "kilometer", "engine_cc", "fuel", "year", "body_type",
                    "transmission", "seats", "number_plate", "exterior_colour",
                    "import_history", "ask_price", "energy_economy", "carbon_emissions"]:
            assert listing.get(key), f"listing['{key}'] is empty: {listing.get(key)}"

    def test_dice_skipped_gracefully(self, completed_job):
        logs = "\n".join(completed_job["logs"])
        assert "DICE_USERNAME / DICE_PASSWORD not set" in logs, logs[-1500:]
        assert "[ERROR] Job failed" not in logs

    def test_photos(self, completed_job):
        urls = completed_job["photos"]["urls"]
        assert 1 <= len(urls) <= 5, f"unexpected photo count: {len(urls)}"
        assert len(set(urls)) == len(urls), "duplicate photo urls"
        for u in urls:
            assert "/photoserver/full/" in u, f"url not converted to full: {u}"
            assert "/photoserver/64x64m/" not in u
        files = completed_job["photos"]["files"]
        assert len(files) == len(urls), f"downloaded {len(files)} of {len(urls)}"

    def test_photo_urls_reachable(self, completed_job):
        url = completed_job["photos"]["urls"][0]
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        assert r.status_code == 200
        assert int(r.headers.get("Content-Length") or len(r.content)) > 1000

    def test_description(self, completed_job):
        desc = completed_job["description"]
        assert isinstance(desc, str) and len(desc) > 100, f"description too short: {len(desc)}"

    def test_no_mongo_id_leak(self, completed_job):
        assert "_id" not in completed_job

    def test_phases_logged(self, completed_job):
        logs = "\n".join(completed_job["logs"])
        assert ">>> Extracting vehicle information" in logs
        assert ">>> Downloading gallery photos" in logs

    def test_close_completed_job(self, api, completed_job):
        r = api.post(f"{BASE_URL}/api/close/{completed_job['job_id']}", timeout=30)
        assert r.status_code == 200
        assert r.json() == {"ok": True}
