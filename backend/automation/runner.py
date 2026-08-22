"""Orchestrator used by the web UI (and reusable by the CLI).

Runs the full Trade Me -> Dice workflow, emitting structured progress events
through a callback. It NEVER clicks the final Post/Submit button: after the
Dice form is filled it emits `ready_for_review` and keeps the browser open
until a close signal (or timeout).
"""

import threading
from dataclasses import asdict
from typing import Callable, Optional

from playwright.sync_api import sync_playwright

from . import config
from .dice import (
    fill_description,
    fill_dice_form,
    fill_dice_ratings,
    login_to_dice,
    select_dice_categories,
    set_dice_listing_options,
    upload_dice_photos,
)
from .photos import download_trade_me_photos, extract_trade_me_photos
from .trade_me import extract_trade_me_listing
from .utils import log

Emit = Callable[[dict], None]

REVIEW_TIMEOUT_SECONDS = 30 * 60  # keep the browser open up to 30 minutes


def _listing_to_dict(listing) -> dict:
    data = asdict(listing)
    # description shown separately; images shown via photos event
    data.pop("images", None)
    return data


def run_job(url: str, emit: Emit, close_event: Optional[threading.Event] = None) -> None:
    """Execute the workflow. `emit` receives dicts the UI understands."""
    if close_event is None:
        close_event = threading.Event()

    try:
        # -------------------------------------------------
        # 1. Trade Me vehicle information + ratings
        # -------------------------------------------------
        emit({"type": "phase", "phase": "trade_me_data",
              "label": "Extracting vehicle information"})

        listing = extract_trade_me_listing(url)

        emit({"type": "data", "listing": _listing_to_dict(listing),
              "description": listing.description})

        emit({"type": "ratings", "ratings": {
            "energy_rating": listing.energy_rating,
            "overall_safety": listing.overall_safety,
            "carbon_rating": listing.carbon_rating,
            "driver_safety": listing.driver_safety,
        }})

        # -------------------------------------------------
        # 2. Trade Me gallery photos (first 5 real thumbnails)
        # -------------------------------------------------
        emit({"type": "phase", "phase": "trade_me_photos",
              "label": "Downloading gallery photos"})

        with sync_playwright() as photo_playwright:
            photo_browser = photo_playwright.chromium.launch(
                headless=not config.HEADED
            )
            photo_context = photo_browser.new_context()
            photo_page = photo_context.new_page()

            try:
                photo_page.goto(url, wait_until="domcontentloaded", timeout=30000)
                photo_page.wait_for_timeout(3000)
                urls = extract_trade_me_photos(photo_page)
                photo_files = download_trade_me_photos(urls)
            finally:
                photo_context.close()
                photo_browser.close()

        emit({"type": "photos",
              "urls": list(urls),
              "files": list(photo_files)})

        # -------------------------------------------------
        # 3. Dice (only if credentials are configured)
        # -------------------------------------------------
        if not (config.DICE_USERNAME and config.DICE_PASSWORD):
            log("[DICE] DICE_USERNAME / DICE_PASSWORD not set — skipping Dice.")
            log("[DICE] Trade Me extraction + photos complete.")
            emit({"type": "status", "status": "completed",
                  "message": "Extraction complete. Set Dice credentials to run the Dice step."})
            emit({"type": "done"})
            return

        emit({"type": "phase", "phase": "dice",
              "label": "Filling Dice advertisement"})

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=not config.HEADED)
            context = browser.new_context()
            page = context.new_page()

            try:
                login_to_dice(page)
                select_dice_categories(page)
                fill_dice_form(page, listing)
                fill_dice_ratings(page, listing)
                fill_description(page, listing.description)
                upload_dice_photos(page, photo_files)
                set_dice_listing_options(page)

                log("")
                log("======================================")
                log(" FORM FILLED — REVIEW MANUALLY")
                log("======================================")
                log("The automation will NOT click Post Ad.")

                emit({"type": "status", "status": "ready_for_review",
                      "message": "Dice form filled. Review it, then close the browser. "
                                 "The ad is NOT submitted."})

                # Keep the browser open for manual review. Never auto-submit.
                close_event.wait(timeout=REVIEW_TIMEOUT_SECONDS)

                log("[DICE] Closing review browser.")
            finally:
                context.close()
                browser.close()

        emit({"type": "status", "status": "completed",
              "message": "Session finished. Ad was never submitted."})
        emit({"type": "done"})

    except Exception as e:
        log(f"[ERROR] Job failed: {e}")
        emit({"type": "status", "status": "error", "message": str(e)})
        emit({"type": "done"})
