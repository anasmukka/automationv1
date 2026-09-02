"""Dice portal automation: login, category flow, field/rating fill, description,
photo upload, tag/location/terms.

Moved verbatim from the original main.py. Changes:
  * print(...) -> log(...)
  * selectors/values imported from config (unchanged strings)
Credentials are read from config (env only) and never logged.
This module NEVER clicks the final Post/Submit button.
"""

from playwright.sync_api import Page

import re

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
    """Fill Dice ratings using their confirmed numeric option values."""

    log("[DICE] Filling vehicle ratings...")

    ratings = {
        "energy_rating": listing.energy_rating,      # exf_41
        "overall_safety": listing.overall_safety,    # exf_42
        "carbon_rating": listing.carbon_rating,      # exf_43
        "driver_safety": listing.driver_safety,      # exf_44
    }

    for field_name, value in ratings.items():
        selector = DICE_RATING_FIELDS[field_name]
        locator = page.locator(selector).first

        try:
            locator.wait_for(state="attached", timeout=5000)
        except Exception:
            log(f"[WARNING] Rating selector not found: {selector}")
            continue

        if value is None or str(value).strip() == "":
            option_value = "-1"

            try:
                locator.select_option(option_value)
                locator.dispatch_event("change")
                log(f"[FILL] {field_name}: None → -1 ({selector})")
            except Exception as e:
                log(
                    f"[ERROR] Could not select "
                    f"{field_name}=-1: {e}"
                )

            continue

        try:
            rating = float(str(value).strip())
        except ValueError:
            log(f"[ERROR] Invalid rating for {field_name}: {value}")
            continue

        if rating < 0 or rating > 6 or (rating * 2) % 1 != 0:
            log(f"[ERROR] Invalid 0.5-step rating for {field_name}: {value}")
            continue

        # Dice rating option values use half-star steps:
        # 0 stars = 0
        # 0.5 stars = 1
        # 1 star = 2
        # 1.5 stars = 3
        # ...
        # 6 stars = 12
        option_value = str(int(rating * 2) + 1)
        try:
            locator.select_option(option_value)
            locator.dispatch_event("change")
            log(
                f"[FILL] {field_name}: "
                f"{option_value} stars ({selector})"
            )
        except Exception as e:
            log(
                f"[ERROR] Could not select "
                f"{field_name}={option_value}: {e}"
            )

# ---------------------------------------------------------
# Dice tag, location and terms
# ---------------------------------------------------------
# ---------------------------------------------------------
# Dice tag, location and terms
# ---------------------------------------------------------
def set_dice_listing_options(page: Page, listing: Listing):
    log("[DICE] Setting tag, location and terms...")

    # Tag
    tag = page.locator("#tagid")

    if tag.count() > 0:
        tag.select_option("1")
        log("[FILL] tag: 1")
    else:
        log("[WARNING] Tag selector #tagid not found.")

    # Location
    location = page.locator("#location")

    if location.count() > 0:
        trade_me_location = (
            listing.location or listing.address or ""
        ).strip()

        if trade_me_location:
            options = location.locator("option")
            matched_value = None

            target = trade_me_location.lower()

            # Also allow "Wiri, Auckland" -> "Auckland"
            parts = [
                part.strip()
                for part in trade_me_location.split(",")
                if part.strip()
            ]
            city = parts[-1].lower() if parts else target

            for i in range(options.count()):
                option = options.nth(i)

                try:
                    text = option.inner_text().strip()
                    value = option.get_attribute("value")

                    if not value:
                        continue

                    text_lower = text.lower()

                    # Exact match
                    if text_lower == target:
                        matched_value = value
                        break

                    # City match
                    if text_lower == city:
                        matched_value = value
                        break

                except Exception:
                    continue

            if matched_value is not None:
                location.scroll_into_view_if_needed()
                location.click()
                location.select_option(matched_value)
                location.dispatch_event("change")

                log(
                    f"[FILL] location: "
                    f"{trade_me_location} -> {matched_value}"
                )
            else:
                log(
                    f"[WARNING] No Dice location matched "
                    f"Trade Me location: {trade_me_location}"
                )
        else:
            log("[SKIP] Dice location: no Trade Me location")
    else:
        log("[WARNING] Location selector #location not found.")

        # Address
    address_value = (
        listing.address or listing.location or ""
    ).strip()

    if not address_value:
        address_value = "."

    address_field = None

    address_selectors = [
        'input[name="address"]',
        'input[id="address"]',
        'textarea[name="address"]',
        'textarea[id="address"]',
        'input[placeholder*="address" i]',
        'textarea[placeholder*="address" i]',
    ]

    for selector in address_selectors:
        candidate = page.locator(selector)

        if candidate.count() > 0:
            address_field = candidate.first
            break

    if address_field is not None:
        try:
            address_field.fill(address_value)
            log(f"[FILL] address: {address_value}")
        except Exception as e:
            log(f"[ERROR] Could not fill address: {e}")
    else:
        log("[WARNING] Dice Address field not found.")

    # Terms
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
# ---------------------------------------------------------
# Description
# ---------------------------------------------------------
def fill_description(page: Page, description: str):
    if not description:
        description = "."
        log("[FILL] Description: . (no source data)")

    log("[DICE] Copying Trade Me description directly.")

    try:
        editor_frame = page.frame_locator("iframe").locator("body")

        editor_frame.click()
        editor_frame.fill(description)

        log("[FILL] Description")

    except Exception as e:
        log(f"[ERROR] Could not fill Description: {e}")