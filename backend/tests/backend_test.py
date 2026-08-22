"""Backend API tests for the Trade Me -> Dice automation service.

Modules under test:
  * server.py            -> /api/health, /api/start, /api/status/{id}, /api/close/{id}
  * automation/runner.py -> job orchestration + graceful Dice skip
  * automation/trade_me.py, automation/photos.py -> extraction assertions
"""

import os
import re
import time

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


# ---------------- full extraction job ----------------
@pytest.fixture(scope="module")
def completed_job(api):
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

        # streaming: log count must have grown across at least two distinct polls
        distinct = sorted(set(counts))
        assert len(distinct) >= 3, f"logs did not stream incrementally: {counts}"
        assert counts == sorted(counts), f"log count decreased: {counts}"
        assert "running" in statuses and statuses[-1] == "completed", statuses

    def test_exact_values_for_sample_listing(self, completed_job):
        listing = completed_job["listing"]
        assert listing["kilometer"] == "39,000 km", listing["kilometer"]
        assert listing["engine_cc"] == "2,996 cc", listing["engine_cc"]
        assert listing["ask_price"] == "$74,990", listing["ask_price"]
        ratings = completed_job["ratings"]
        assert [ratings["energy_rating"], ratings["overall_safety"],
                ratings["carbon_rating"], ratings["driver_safety"]] == \
            ["1.5", "5", "1.5", "5"], ratings
        assert len(completed_job["photos"]["urls"]) == 5
        assert len(completed_job["description"]) > 2000, len(completed_job["description"])

    def test_status_completed(self, completed_job):
        assert completed_job["status"] == "completed", completed_job.get("error") or completed_job.get("message")
        assert completed_job["done"] is True
        assert completed_job["error"] is None

    def test_dice_skipped_gracefully(self, completed_job):
        logs = "\n".join(completed_job["logs"])
        assert "DICE_USERNAME / DICE_PASSWORD not set" in logs, logs[-1500:]
        assert "[ERROR] Job failed" not in logs

    def test_listing_fields(self, completed_job):
        listing = completed_job["listing"]
        assert isinstance(listing, dict)
        for key in ["title", "kilometer", "engine_cc", "fuel", "year", "body_type",
                    "transmission", "seats", "number_plate", "exterior_colour",
                    "import_history", "ask_price", "energy_economy", "carbon_emissions"]:
            assert listing.get(key), f"listing['{key}'] is empty: {listing.get(key)}"

    def test_kilometer_format_not_swapped(self, completed_job):
        km = completed_job["listing"]["kilometer"]
        assert re.fullmatch(r"[\d,]+\s*km", km, re.IGNORECASE), f"bad odometer value: {km!r}"
        assert "," in km, f"comma stripped from odometer: {km!r}"
        assert "cc" not in km.lower()

    def test_engine_format_not_swapped(self, completed_job):
        cc = completed_job["listing"]["engine_cc"]
        assert re.fullmatch(r"[\d,]+\s*cc", cc, re.IGNORECASE), f"bad engine value: {cc!r}"
        assert "," in cc, f"comma stripped from engine: {cc!r}"
        assert "km" not in cc.lower()

    def test_ask_price_has_dollar(self, completed_job):
        assert completed_job["listing"]["ask_price"].startswith("$")

    def test_ratings(self, completed_job):
        ratings = completed_job["ratings"]
        assert isinstance(ratings, dict)
        for key in ["energy_rating", "overall_safety", "carbon_rating", "driver_safety"]:
            val = ratings.get(key)
            assert val is not None, f"rating {key} missing"
            assert re.fullmatch(r"[0-9]+(?:\.5)?", str(val)), f"rating {key} not numeric: {val!r}"
            assert 0 <= float(val) <= 5

    def test_photos(self, completed_job):
        urls = completed_job["photos"]["urls"]
        assert 1 <= len(urls) <= 5, f"unexpected photo count: {len(urls)}"
        assert len(set(urls)) == len(urls), "duplicate photo urls"
        for u in urls:
            assert "/photoserver/full/" in u, f"url not converted to full: {u}"
            assert "/photoserver/64x64m/" not in u
        files = completed_job["photos"]["files"]
        assert len(files) == len(urls), f"downloaded {len(files)} of {len(urls)}"
        for f in files:
            assert f.startswith("/app/temp_photos/")

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
