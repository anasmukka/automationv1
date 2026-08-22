"""Scratch test: download 5 photos to temp_photos/ and upload them to Dice.

Credentials come from environment variables (never hardcoded).
Run: HEADED=true python upload_test.py
"""

import os
from pathlib import Path
from urllib.request import urlopen, Request

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv("backend/.env")

DICE_USERNAME = os.getenv("DICE_USERNAME")
DICE_PASSWORD = os.getenv("DICE_PASSWORD")

TEMP_DIR = Path("temp_photos")
TEMP_DIR.mkdir(exist_ok=True)

# Delete photos from the previous job
for file in TEMP_DIR.iterdir():
    if file.is_file():
        file.unlink()

photo_urls = [
    "https://trademe.tmcdn.co.nz/photoserver/full/2324008677.jpg",
    "https://trademe.tmcdn.co.nz/photoserver/full/2324008678.jpg",
    "https://trademe.tmcdn.co.nz/photoserver/full/2312092492.jpg",
    "https://trademe.tmcdn.co.nz/photoserver/full/2324008679.jpg",
    "https://trademe.tmcdn.co.nz/photoserver/full/2320393140.jpg",
]

print("[PHOTOS] Downloading first 5 images...")

downloaded_files = []

for i, url in enumerate(photo_urls, 1):
    file_path = TEMP_DIR / f"photo_{i}.jpg"

    request = Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"}
    )

    with urlopen(request) as response:
        file_path.write_bytes(response.read())

    downloaded_files.append(str(file_path))
    print(f"[DOWNLOAD] Photo {i}: {file_path}")

print(f"\n[PHOTOS] Downloaded {len(downloaded_files)} photos.")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()

    page.goto("https://may2026karnataka.dicewebfreelancers.com/index.php")

    page.get_by_role("textbox", name="Username").fill(DICE_USERNAME)
    page.get_by_role("textbox", name="Password").fill(DICE_PASSWORD)
    page.get_by_role("checkbox", name="Remember Me").check()
    page.get_by_role("button", name="Log in").click()

    page.get_by_role("button", name="Choose File").set_input_files(
        downloaded_files
    )

    print("[DICE] 5 photos selected.")

    input("\nCheck Dice. Press Enter to close...")

    browser.close()
