"""Scratch test: Dice login + category flow + TinyMCE description fill.

Credentials come from environment variables (never hardcoded).
Run: HEADED=true python test.py
"""

import os

from dotenv import load_dotenv
from playwright.sync_api import Playwright, sync_playwright

load_dotenv("backend/.env")

DICE_USERNAME = os.getenv("DICE_USERNAME")
DICE_PASSWORD = os.getenv("DICE_PASSWORD")


def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://indonesiadata.dicewebfreelancers.com/")
    page.get_by_role("textbox", name="Username").click()
    page.get_by_role("textbox", name="Username").fill(DICE_USERNAME)
    page.get_by_role("textbox", name="Password").click()
    page.get_by_role("textbox", name="Password").fill(DICE_PASSWORD)
    page.get_by_role("button", name="Log in").click()
    page.locator("#title").click()
    page.locator("#title").fill("TEst")
    page.locator("#category").select_option("1")
    page.locator("#jomcl_category_-1_1 #category").select_option("6")
    page.locator("#jomcl_category_6_1 #category").select_option("8")
    page.locator("#jomcl_category_8_1 #category").select_option("35")
    page.get_by_text("Description Edit Insert View").click()
    print("IFRAMES:", page.locator("iframe").count())

    editor_frame = page.frame_locator("iframe").locator("body")

    editor_frame.click()
    editor_frame.fill("TEST DESCRIPTION 123")

    print("DESCRIPTION TEST COMPLETE")
    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
