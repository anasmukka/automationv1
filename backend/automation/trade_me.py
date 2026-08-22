"""Trade Me extraction (vehicle info + star ratings).

Logic moved verbatim from the original main.py. The ONLY changes:
  * print(...) -> log(...)
  * headless=False -> headless=not HEADED
Selectors and extraction rules are untouched.
"""

import re

from playwright.sync_api import sync_playwright

from .config import HEADED
from .models import Listing
from .utils import log


def extract_trade_me_listing(url: str) -> Listing:
    log("[TRADE ME] Opening listing...")
    log(f"[TRADE ME] URL: {url}")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not HEADED)
        context = browser.new_context()
        page = context.new_page()

        try:
            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=30000
            )

            page.wait_for_timeout(3000)

            log("[TRADE ME] Page loaded.")
            log("[TRADE ME] Extracting vehicle information...")

            # -------------------------------------------------
            # Open "Show all basic details"
            # -------------------------------------------------
            try:
                show_details = page.get_by_text(
                    "Show all basic details",
                    exact=True
                )

                if show_details.count() > 0:
                    log("[TRADE ME] Opening full vehicle information...")
                    show_details.first.click()
                    page.wait_for_timeout(1000)
                else:
                    log("[TRADE ME] No 'Show all basic details' dialog — reading visible page.")

            except Exception as e:
                log(f"[TRADE ME] Could not open full details: {e}")

            body_text = page.locator("body").inner_text()

            # -------------------------------------------------
            # Read Vehicle Information popup separately
            # -------------------------------------------------
            vehicle_details_text = ""

            try:
                dialogs = page.locator('[role="dialog"]')

                if dialogs.count() > 0:
                    vehicle_details_text = dialogs.last.inner_text()
                else:
                    vehicle_info = page.get_by_text(
                        "Vehicle information",
                        exact=True
                    )

                    if vehicle_info.count() > 0:
                        parent = vehicle_info.last.locator("xpath=..")

                        for _ in range(5):
                            try:
                                text = parent.inner_text()

                                if (
                                    "Odometer" in text
                                    and "Engine size" in text
                                ):
                                    vehicle_details_text = text
                                    break

                                parent = parent.locator("xpath=..")
                            except Exception:
                                break

            except Exception as e:
                log(f"[TRADE ME] Vehicle popup extraction warning: {e}")

            if vehicle_details_text:
                log("[TRADE ME] Vehicle information popup captured.")
            else:
                log("[TRADE ME] Vehicle information popup not detected.")

            # -------------------------------------------------
            # Helpers
            # -------------------------------------------------
            def find_regex(pattern, text=None):
                source = text if text is not None else body_text
                match = re.search(pattern, source, re.IGNORECASE)

                if match:
                    return match.group(1).strip()

                return None

            def find_value(label, text):
                lines = [
                    line.strip()
                    for line in text.splitlines()
                    if line.strip()
                ]

                for i, line in enumerate(lines):
                    if line.lower() == label.lower():
                        if i + 1 < len(lines):
                            return lines[i + 1].strip()

                return None

            # -------------------------------------------------
            # Title
            # -------------------------------------------------
            title = None

            page_title = page.title()

            if page_title:
                title = re.sub(
                    r"\s*\|\s*Trade Me Motors.*$",
                    "",
                    page_title,
                    flags=re.IGNORECASE
                ).strip()

            # -------------------------------------------------
            # Asking price
            # KEEP THE $
            # -------------------------------------------------
            price = find_regex(r"Asking price:\s*(\$\s*[\d,]+)")

            # -------------------------------------------------
            # Previous price
            # -------------------------------------------------
            previous_price = find_regex(r"Was\s*(\$\s*[\d,]+)")

           # -------------------------------------------------
            # Odometer (km) + Engine (cc)
            #
            # Read from the CURRENT VISIBLE PAGE first (badges/body text),
            # falling back to the details modal only if it exists. This never
            # depends on clicking a "Show more details" element.
            #
            # The value is kept EXACTLY as shown on the source, INCLUDING the
            # unit and the source spacing:
            #   "262,000km" -> "262,000km"      "39,000 km" -> "39,000 km"
            #   "4477cc"    -> "4477cc"         "4,477cc"   -> "4,477cc"
            # The km and cc patterns are unit-specific, so they can never swap.
            # -------------------------------------------------
            log("[TRADE ME] Reading vehicle badges...")

            def find_first(patterns, *sources):
                for src in sources:
                    if not src:
                        continue
                    for pat in patterns:
                        m = re.search(pat, src, re.IGNORECASE)
                        if m:
                            return m.group(1).strip()
                return None

            kilometer = find_first(
                [
                    r"odometer\s*[:\r\n]*\s*((?:\d{1,3}(?:,\d{3})+|\d{4,})\s*km)",
                    r"(?<![\d/])((?:\d{1,3}(?:,\d{3})+|\d{4,})\s*km)\b",
                ],
                body_text,
                vehicle_details_text,
            )

            if kilometer:
                log(f"[TRADE ME] KM: {kilometer}")
            else:
                log("[WARN] Could not find kilometres")

            engine_cc = find_first(
                [
                    r"engine\s*(?:size)?\s*[:\r\n]*\s*((?:\d{3,}(?:,\d{3})*|\d{1,3}(?:,\d{3})+)\s*cc)",
                    r"(?<![\d/])((?:\d{3,}(?:,\d{3})*|\d{1,3}(?:,\d{3})+)\s*cc)\b",
                ],
                body_text,
                vehicle_details_text,
            )

            if engine_cc:
                log(f"[TRADE ME] Engine: {engine_cc}")
            else:
                log("[WARN] Could not find engine capacity")

            # -------------------------------------------------
            # Basic vehicle details
            # -------------------------------------------------
            fuel = None

            for possible in [
                "Petrol",
                "Diesel",
                "Hybrid",
                "Electric",
                "LPG",
            ]:
                if re.search(rf"\b{re.escape(possible)}\b", body_text, re.IGNORECASE):
                    fuel = possible
                    break

            if fuel:
                log(f"[TRADE ME] Fuel: {fuel}")
            else:
                log("[WARN] Could not find fuel type")

            transmission = None

            for possible in [
                "Automatic",
                "Manual",
            ]:
                if re.search(rf"\b{re.escape(possible)}\b", body_text, re.IGNORECASE):
                    transmission = possible
                    break

            body_type = None

            for possible in [
                "RV/SUV",
                "SUV",
                "Sedan",
                "Hatchback",
                "Station Wagon",
                "Wagon",
                "Convertible",
                "Coupe",
                "Van",
                "Ute",
                "People Mover",
                "Sports Car",
            ]:
                if re.search(rf"\b{re.escape(possible)}\b", body_text, re.IGNORECASE):
                    body_type = possible
                    break

            if body_type:
                log(f"[TRADE ME] Body: {body_type}")
            else:
                log("[WARN] Could not find body type")

            if transmission:
                log(f"[TRADE ME] Transmission: {transmission}")
            else:
                log("[WARN] Could not find transmission")

            # -------------------------------------------------
            # Doors
            # -------------------------------------------------
            doors = find_regex(r"Doors\s+(\d+)")

            if not doors:
                doors = find_regex(r"(\d+)\s*doors?")

            # -------------------------------------------------
            # Seats
            # -------------------------------------------------
            seats = find_regex(r"Seats\s+(\d+)")

            if not seats:
                seats = find_regex(r"(\d+)\s*seats?")

            # -------------------------------------------------
            # Number plate
            # Resilient across layouts: reads the visible page first, then the
            # details modal. Case-sensitive uppercase token (2-7 chars) right
            # after the "Number plate" / "Plate" label so it will NOT mistake
            # a following word (e.g. "history") for the plate.
            # -------------------------------------------------
            number_plate = None

            for src in (body_text, vehicle_details_text):
                if not src:
                    continue
                m = re.search(
                    r"(?i:number\s*plate)[\s:\r\n]+([A-Z0-9]{2,7})\b",
                    src,
                )
                if not m:
                    m = re.search(
                        r"(?i:\bplate\b)[\s:\r\n]+([A-Z0-9]{2,7})\b",
                        src,
                    )
                if m:
                    number_plate = m.group(1).strip().upper()
                    break

            if number_plate:
                log(f"[TRADE ME] Number plate: {number_plate}")
            else:
                log("[WARN] Could not find number plate")

            # -------------------------------------------------
            # Year
            # -------------------------------------------------
            year = find_regex(r"Year\s+((?:19|20)\d{2})")

            if not year and title:
                match = re.search(r"\b(19\d{2}|20\d{2})\b", title)

                if match:
                    year = match.group(1)

            # -------------------------------------------------
            # Exterior colour
            # -------------------------------------------------
            exterior_colour = find_regex(r"Exterior colour\s+(.+)")

            if exterior_colour:
                exterior_colour = re.sub(
                    r"\s+exterior$",
                    "",
                    exterior_colour,
                    flags=re.IGNORECASE
                ).strip()

            # Fallback for the basic-details text
            if not exterior_colour:
                exterior_colour = find_regex(r"([A-Za-z][A-Za-z ]+)\s+exterior")

                if exterior_colour:
                    exterior_colour = exterior_colour.strip()

            # -------------------------------------------------
            # Import history
            # -------------------------------------------------
            import_history = find_regex(r"Import history\s+(.+)")

            if not import_history:
                if re.search(r"\bNZ New\b", body_text, re.IGNORECASE):
                    import_history = "NZ New"
                elif re.search(r"\bImported\b", body_text, re.IGNORECASE):
                    import_history = "Imported"

            # -------------------------------------------------
            # On-road costs
            # -------------------------------------------------
            on_road_costs = find_regex(r"On road costs\s+([^\n]+)")

            # -------------------------------------------------
            # Energy economy
            # -------------------------------------------------
            energy_economy = find_regex(r"Energy economy\s+([\d.]+\s*L\s*/\s*100km)")

            if not energy_economy:
                energy_economy = find_regex(r"([\d.]+\s*L\s*/\s*100km)")

            # -------------------------------------------------
            # Carbon emissions
            # -------------------------------------------------
            carbon_emissions = find_regex(r"Carbon emissions\s+(\d+\s*grams/km)")

            # -------------------------------------------------
            # Star ratings
            # -------------------------------------------------
            def extract_star_rating(label):
                try:
                    label_locator = page.get_by_text(
                        label,
                        exact=True
                    )

                    if label_locator.count() == 0:
                        return None

                    # The rating star is inside the same rating card.
                    card = label_locator.first.locator(
                        "xpath=ancestor::*[.//div[contains(@class, 'tm-listing-rating-star__blue')]][1]"
                    )

                    rating = card.locator(
                        "div.tm-listing-rating-star__blue[aria-label]"
                    )

                    if rating.count() == 0:
                        return None

                    aria = rating.first.get_attribute("aria-label")

                    if not aria:
                        return None

                    match = re.search(
                        r"([0-9]+(?:\.5)?)\s+out of\s+[0-9]+\s+stars",
                        aria,
                        re.IGNORECASE
                    )

                    if match:
                        return match.group(1)

                except Exception as e:
                    log(f"[TRADE ME] Rating extraction warning for {label}: {e}")

                return None

            log("[TRADE ME] Reading ratings...")

            def read_rating(label, log_name):
                value = extract_star_rating(label)
                if value is None:
                    log(f"[WARN] Could not find {log_name} rating")
                else:
                    log(f"[RATING] {log_name}: {value}")
                return value

            energy_rating = read_rating("Energy economy", "Energy Economy")
            overall_safety = read_rating("Overall safety", "Overall Safety")
            carbon_rating = read_rating("Carbon emissions", "Carbon Emissions")
            driver_safety = read_rating("Driver Safety", "Driver Safety")

            # -------------------------------------------------
            # Description
            # -------------------------------------------------
            description = ""

            try:
                match = re.search(
                    r"Description\s+(.*?)(?:Show more|More model information)",
                    body_text,
                    re.IGNORECASE | re.DOTALL
                )

                if match:
                    description = match.group(1).strip()

            except Exception:
                description = ""

            # -------------------------------------------------
            # Print extracted data
            # -------------------------------------------------
            log("")
            log("=" * 60)
            log("EXTRACTED TRADE ME DATA")
            log("=" * 60)

            extracted = {
                "title": title,
                "kilometer": kilometer,
                "fuel": fuel,
                "engine_cc": engine_cc,
                "body_type": body_type,
                "transmission": transmission,
                "cylinders": None,
                "year": year,
                "number_plate": number_plate,
                "exterior_colour": exterior_colour,
                "doors": doors,
                "import_history": import_history,
                "price": price,
                "previous_price": previous_price,
                "on_road_costs": on_road_costs,
                "seats": seats,
                "energy_economy": energy_economy,
                "carbon_emissions": carbon_emissions,
                "energy_rating": energy_rating,
                "overall_safety": overall_safety,
                "carbon_rating": carbon_rating,
                "driver_safety": driver_safety,
            }

            for key, value in extracted.items():
                log(f"{key:20} : {value}")

            log("=" * 60)

            # -------------------------------------------------
            # Return Listing
            # -------------------------------------------------
            return Listing(
                title=title,
                kilometer=kilometer,
                fuel=fuel,
                engine_cc=engine_cc,
                body_type=body_type,
                transmission=transmission,
                cylinders=None,
                year=year,
                number_plate=number_plate,
                exterior_colour=exterior_colour,
                doors=doors,
                import_history=import_history,
                ask_price=price,
                buy_price=None,
                starting_price=None,
                on_road_costs=on_road_costs,
                seats=seats,
                energy_economy=energy_economy,
                carbon_emissions=carbon_emissions,
                energy_rating=energy_rating,
                overall_safety=overall_safety,
                carbon_rating=carbon_rating,
                driver_safety=driver_safety,
                source_link=url,
                listed_on=None,
                price=None,
                description=description,
            )

        finally:
            context.close()
            browser.close()
