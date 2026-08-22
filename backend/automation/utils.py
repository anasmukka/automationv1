"""Shared helpers + a tiny log() sink.

log() prints to the console exactly like the original code AND forwards each
line to any registered listeners (used by the web UI to stream progress).
Passwords are never passed to log().
"""

import re
from typing import Callable, Optional

from playwright.sync_api import Page

# ---------------------------------------------------------
# Logging sink (single-job local tool -> a simple listener list is enough)
# ---------------------------------------------------------
_listeners: list[Callable[[str], None]] = []


def add_log_listener(fn: Callable[[str], None]) -> None:
    _listeners.append(fn)


def remove_log_listener(fn: Callable[[str], None]) -> None:
    if fn in _listeners:
        _listeners.remove(fn)


def log(message: str) -> None:
    print(message)
    for fn in list(_listeners):
        try:
            fn(message)
        except Exception:
            pass


# ---------------------------------------------------------
# Value helpers (moved verbatim)
# ---------------------------------------------------------
def clean_number(value: str) -> str:
    """
    Convert:
        119,638 km -> 119638
        1,998 cc   -> 1998
    """
    return re.sub(r"[^\d.]", "", value)


def fill_if_available(page: Page, selector: str, value: Optional[str]) -> None:
    """
    NEVER fill a Dice field if we don't have source information.
    """
    if value is None:
        return

    value = str(value).strip()

    if not value:
        return

    locator = page.locator(selector)

    if locator.count() == 0:
        log(f"[WARNING] Selector not found: {selector}")
        return

    locator.first.fill(value)
