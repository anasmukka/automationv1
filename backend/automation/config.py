"""Central configuration: credentials, selectors, paths, HEADED flag.

Nothing here is listing-specific. Credentials come from environment variables
only (never hardcoded, never logged).
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load backend/.env (this file lives in backend/automation/)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# ---------------------------------------------------------
# Dice target + credentials
# ---------------------------------------------------------
DICE_URL = os.getenv(
    "DICE_URL",
    "https://indonesiadata.dicewebfreelancers.com/",
)

DICE_USERNAME = os.getenv("DICE_USERNAME")
DICE_PASSWORD = os.getenv("DICE_PASSWORD")


def _as_bool(value: str) -> bool:
    return str(value).strip().lower() in ("1", "true", "yes", "on")


# When HEADED=true a visible browser window opens (use this on your own
# machine). In the cloud container leave it false so Chromium runs headless.
HEADED = _as_bool(os.getenv("HEADED", "false"))

# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------
# Repo root is two levels up from this file (backend/automation/config.py).
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TEMP_PHOTOS_DIR = Path(os.getenv("TEMP_PHOTOS_DIR", PROJECT_ROOT / "temp_photos"))

# ---------------------------------------------------------
# Dice selectors discovered from Codegen (do not guess-replace)
# ---------------------------------------------------------
DICE_FIELDS = {
    "title": "#title",

    "kilometer": "#exf_25",
    "fuel": "#exf_28",
    "engine_cc": "#exf_29",
    "body_type": "#exf_26",
    "transmission": "#exf_30",
    "cylinders": "#exf_34",
    "year": "#exf_32",
    "number_plate": "#exf_31",
    "exterior_colour": "#exf_33",
    "doors": "#exf_35",
    "import_history": "#exf_36",

    "ask_price": "#exf_37",
    "buy_price": "#exf_38",
    "starting_price": "#exf_39",
    "on_road_costs": "#exf_40",

    "seats": "#exf_27",

    "source_link": "#exf_46",
    "listed_on": "#exf_45",

    "price": 'input[placeholder="0.00"]',
}

DICE_RATING_FIELDS = {
    "energy_rating": "#exf_41",
    "overall_safety": "#exf_42",
    "carbon_rating": "#exf_43",
    "driver_safety": "#exf_44",
}

# Price-type fields never receive the "." missing-data fallback.
PRICE_FIELDS = {
    "price",
    "ask_price",
}