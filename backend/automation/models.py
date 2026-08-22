"""Canonical listing data model (moved verbatim from the original main.py)."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Listing:
    title: Optional[str] = None
    kilometer: Optional[str] = None
    fuel: Optional[str] = None
    engine_cc: Optional[str] = None
    body_type: Optional[str] = None
    transmission: Optional[str] = None
    cylinders: Optional[str] = None
    year: Optional[str] = None
    number_plate: Optional[str] = None
    exterior_colour: Optional[str] = None
    doors: Optional[str] = None
    import_history: Optional[str] = None
    ask_price: Optional[str] = None
    buy_price: Optional[str] = None
    starting_price: Optional[str] = None
    on_road_costs: Optional[str] = None
    seats: Optional[str] = None
    energy_economy: Optional[str] = None
    carbon_emissions: Optional[str] = None

    # Trade Me star ratings
    energy_rating: Optional[str] = None
    overall_safety: Optional[str] = None
    carbon_rating: Optional[str] = None
    driver_safety: Optional[str] = None

    source_link: Optional[str] = None
    listed_on: Optional[str] = None
    price: Optional[str] = None

    description: str = ""
    images: list[str] = field(default_factory=list)

    address: Optional[str] = None
    location: Optional[str] = None
    country: Optional[str] = None
