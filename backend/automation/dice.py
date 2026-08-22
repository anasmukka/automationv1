"""Dice portal automation: login, category flow, field/rating fill, description,
photo upload, tag/location/terms.

Moved verbatim from the original main.py. Changes:
  * print(...) -> log(...)
  * selectors/values imported from config (unchanged strings)
Credentials are read from config (env only) and never logged.
This module NEVER clicks the final Post/Submit button.
"""

from playwright.sync_api import Page

from .config import (
    DICE_URL,
    DICE_USERNAME,
    DICE_PASSWORD,
    DICE_FIELDS,
    DICE_RATING_FIELDS,
    PRICE_FIELDS,
)
from .models import Listing
from .utils import fill_if_available, log


# ---------------------------------------------------------
# Dice login
# ---------------------------------------------------------
def login_to_dice(page: Page):
    log("[DICE] Opening Dice...")

    page.goto(DICE_URL, wait_until="domcontentloaded")

    log("[DICE] Logging in...")

    page.get_by_role("textbox", name="Username").fill(DICE_USERNAME)
    page.get_by_role("textbox", name="Password").fill(DICE_PASSWORD)

    remember = page.get_by_role("checkbox", name="Remember Me")

    if remember.count() > 0:
        remember.check()

    page.get_by_role("button", name="Log in").click()

    page.wait_for_load_state("domcontentloaded")

    log("[DICE] Login completed.")


# ---------------------------------------------------------
# Dice category selection
# ---------------------------------------------------------
def select_dice_categories(page: Page):
    log("[DICE] Selecting categories...")

    # 1. Main category -> Vehicles
    page.locator("#category").select_option("6")

    # 2. Subcategory -> Cars - Parts
    page.locator(
        "#jomcl_category_6_1 #category"
    ).select_option("8")

    # 3. Subcategory -> Second hand cars in Newzeland
    page.locator(
        "#jomcl_category_8_1 #category"
    ).select_option("32")

    log("[DICE] Categories selected.")
    log("[DICE] Waiting for vehicle fields to appear...")

    # Give Dice's JavaScript time to create the dynamic fields.
    page.wait_for_timeout(2000)

    # Diagnostic information
    log(f"URL: {page.url}")
    log(f"exf_25 count: {page.locator('#exf_25').count()}")
    log(f"exf_26 count: {page.locator('#exf_26').count()}")
    log(f"exf_27 count: {page.locator('#exf_27').count()}")

    # Save a screenshot so we can see exactly what Dice generated.
    page.screenshot(
        path="dice_after_categories.png",
        full_page=True
    )

    log("[DICE] Category/form check complete.")


# ---------------------------------------------------------
# Fill Dice vehicle form
# ---------------------------------------------------------
def fill_dice_form(page: Page, listing: Listing):

    log("[DICE] Filling available fields...")

    values = {
        "title": listing.title,

        # Preserve Trade Me source formatting exactly, e.g. "55,830 km"
        "kilometer": listing.kilometer if listing.kilometer else None,

        "fuel": listing.fuel,

        # Preserve Trade Me source formatting exactly, e.g. "1,298 cc"
        "engine_cc": listing.engine_cc if listing.engine_cc else None,

        "body_type": listing.body_type,
        "transmission": listing.transmission,
        "cylinders": listing.cylinders,
        "year": listing.year,
        "number_plate": listing.number_plate,
        "exterior_colour": listing.exterior_colour,
        "doors": listing.doors,
        "import_history": listing.import_history,

        "ask_price": listing.ask_price,
        "buy_price": listing.buy_price,
        "starting_price": listing.starting_price,
        "on_road_costs": listing.on_road_costs,

        "seats": listing.seats,

        "source_link": listing.source_link,
        "listed_on": listing.listed_on,

        "price": listing.price,
    }

    for field_name, value in values.items():

        selector = DICE_FIELDS[field_name]

        if value is None:
            if field_name in PRICE_FIELDS:
                log(f"[SKIP] {field_name}: no source data")
                continue

            value = "."
            log(f"[FILL] {field_name}: . (no source data)")
        else:
            log(f"[FILL] {field_name}: {value}")

        fill_if_available(
            page,
            selector,
            value
        )


# ---------------------------------------------------------
# Dice star ratings
# ---------------------------------------------------------
def fill_dice_ratings(page: Page, listing: Listing):
    log("[DICE] Filling vehicle ratings...")

    ratings = {
        "energy_rating": listing.energy_rating,
        "overall_safety": listing.overall_safety,
        "carbon_rating": listing.carbon_rating,
        "driver_safety": listing.driver_safety,
    }

    for field_name, value in ratings.items():
        selector = DICE_RATING_FIELDS[field_name]

        if value is None:
            # Rating dropdowns do not have a "." option.
            # Leave them at Dice's default "- None -" when Trade Me has no rating.
            log(f"[SKIP] {field_name}: no source rating")
            continue

        try:
            locator = page.locator(selector)

            if locator.count() == 0:
                log(f"[WARNING] Rating selector not found: {selector}")
                continue

            locator.first.select_option(str(value))
            log(f"[FILL] {field_name}: {value} stars")

        except Exception as e:
            log(f"[ERROR] Could not fill {field_name}: {e}")


# ---------------------------------------------------------
# Dice tag, location and terms
# ---------------------------------------------------------
def set_dice_listing_options(page: Page):
    log("[DICE] Setting tag, location and terms...")

    tag = page.locator("#tagid")
    if tag.count() > 0:
        tag.select_option("1")
        log("[FILL] tag: 1")
    else:
        log("[WARNING] Tag selector #tagid not found.")

    location = page.locator("#location")
    if location.count() > 0:
        location.select_option("34")
        log("[FILL] location: 34")
    else:
        log("[WARNING] Location selector #location not found.")

    terms = page.get_by_role(
        "checkbox",
        name="By submitting this form you"
    )

    if terms.count() > 0:
        if not terms.first.is_checked():
            terms.first.check()
        log("[FILL] terms: checked")
    else:
        log("[WARNING] Terms checkbox not found.")


# ---------------------------------------------------------
# Description
# ---------------------------------------------------------
def fill_description(page: Page, description: str):

    if not description:
        description = "."
        log("[FILL] Description: . (no source data)")

    log("[DICE] Copying Trade Me description directly.")

    try:
        # Dice uses a TinyMCE rich-text editor inside an iframe.
        editor_frame = page.frame_locator("iframe").locator("body")

        editor_frame.click()
        editor_frame.fill(description)

        log("[FILL] Description")

    except Exception as e:
        log(f"[ERROR] Could not fill Description: {e}")


# ---------------------------------------------------------
# Dice photo upload
# ---------------------------------------------------------
def upload_dice_photos(page: Page, photo_files):
    if not photo_files:
        log("[SKIP] Photos: no photos downloaded")
        return

    log(f"[DICE] Uploading {len(photo_files)} photos...")

    choose_file = page.get_by_role("button", name="Choose File")

    if choose_file.count() == 0:
        log("[WARNING] Choose File button not found.")
        return

    try:
        choose_file.first.set_input_files(list(photo_files))
        log(f"[FILL] Photos: {len(photo_files)} uploaded")
    except Exception as e:
        log(f"[ERROR] Could not upload photos: {e}")
