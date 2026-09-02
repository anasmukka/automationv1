"""CLI entry point — preserves the original interactive workflow.

Run this on your own machine with HEADED=true (in .env) to watch a visible
browser. It extracts the Trade Me listing, downloads the first 5 gallery
photos, fills the Dice ad, then STOPS at page.pause() for manual review.
It NEVER clicks the final Post/Submit button.

The heavy lifting lives in backend/automation/ (single source of truth,
shared with the web UI). This file just wires the steps together like the
original main.py did.
"""

import sys
from pathlib import Path

# Make the automation package importable when running from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

from playwright.sync_api import sync_playwright

from automation import config
from automation.dice import (
    fill_description,
    fill_dice_form,
    fill_dice_ratings,
    login_to_dice,
    select_dice_categories,
    set_dice_listing_options,
    upload_dice_photos,
)
from automation.photos import download_trade_me_photos, extract_trade_me_photos
from automation.trade_me import extract_trade_me_listing


def main():
    if not config.DICE_USERNAME or not config.DICE_PASSWORD:
        raise RuntimeError("DICE_USERNAME and DICE_PASSWORD must be set in .env")

    trade_me_url = input("Enter Trade Me listing URL: ").strip()

    if not trade_me_url:
        print("No URL supplied.")
        return

    print()
    print("======================================")
    print(" Trade Me -> Dice Automation V1")
    print("======================================")
    print()

    listing = extract_trade_me_listing(trade_me_url)

    # Extract and download the first 5 Trade Me gallery photos.
    with sync_playwright() as photo_playwright:
        photo_browser = photo_playwright.chromium.launch(headless=not config.HEADED)
        photo_context = photo_browser.new_context()
        photo_page = photo_context.new_page()

        try:
            photo_page.goto(trade_me_url, wait_until="domcontentloaded", timeout=30000)
            photo_page.wait_for_timeout(3000)
            urls = extract_trade_me_photos(photo_page)
            photo_files = download_trade_me_photos(urls)
        finally:
            photo_context.close()
            photo_browser.close()

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
            set_dice_listing_options(page, listing)

            print()
            print("======================================")
            print(" FORM FILLED — REVIEW MANUALLY")
            print("======================================")
            print()
            print("The script will NOT click Post Ad.")
            print("Close the browser when finished reviewing.")

            page.pause()

        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    main()
