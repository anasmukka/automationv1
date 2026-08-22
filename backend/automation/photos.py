"""Trade Me gallery photo extraction + download.

Moved verbatim from the original main.py. Changes:
  * print(...) -> log(...)
  * temp folder path comes from config.TEMP_PHOTOS_DIR
  * per-photo try/except so one bad download reports which photo failed
    instead of crashing the whole job (matches the error-handling spec).
"""

from collections.abc import Sequence
from urllib.request import urlopen, Request

from .config import TEMP_PHOTOS_DIR
from .utils import log


class photo_urls(Sequence):
    """Ordered collection of unique, non-empty gallery photo URLs."""

    def __init__(self, urls=()):
        self._urls = []
        for url in urls:
            url = str(url).strip()
            if url and url not in self._urls:
                self._urls.append(url)

    def __getitem__(self, index):
        return self._urls[index]

    def __len__(self):
        return len(self._urls)

    def __repr__(self):
        return f"photo_urls({self._urls!r})"


class downloaded_files(Sequence):
    """Ordered collection of unique, non-empty downloaded file paths."""

    def __init__(self, paths=()):
        self._paths = []
        for path in paths:
            path = str(path).strip()
            if path and path not in self._paths:
                self._paths.append(path)

    def __getitem__(self, index):
        return self._paths[index]

    def __len__(self):
        return len(self._paths)

    def __repr__(self):
        return f"downloaded_files({self._paths!r})"


def extract_trade_me_photos(page):
    log("[TRADE ME] Extracting gallery photos...")

    thumbnails = page.locator("img.tm-gallery-view__thumbnail")
    count = thumbnails.count()

    log(f"[TRADE ME] Gallery thumbnails found: {count}")

    urls = []

    for i in range(min(count, 5)):
        src = thumbnails.nth(i).get_attribute("src")

        if not src:
            continue

        image_url = src.replace(
            "/photoserver/64x64m/",
            "/photoserver/full/"
        )

        if image_url not in urls:
            urls.append(image_url)

    photos = photo_urls(urls)

    log(f"[TRADE ME] Selected {len(photos)} photos.")

    for i, url in enumerate(photos, 1):
        log(f"[PHOTO {i}] {url}")

    return photos


def download_trade_me_photos(photo_urls):
    temp_dir = TEMP_PHOTOS_DIR
    temp_dir.mkdir(exist_ok=True)

    # Remove photos from previous job
    for file in temp_dir.iterdir():
        if file.is_file():
            file.unlink()

    downloaded = []

    log("[PHOTOS] Downloading selected photos...")

    for i, url in enumerate(photo_urls, 1):
        file_path = temp_dir / f"photo_{i}.jpg"

        request = Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"}
        )

        try:
            with urlopen(request) as response:
                file_path.write_bytes(response.read())

            downloaded.append(str(file_path))
            log(f"[DOWNLOAD] Photo {i}: {file_path}")

        except Exception as e:
            log(f"[ERROR] Photo {i} download failed ({url}): {e}")

    log(f"[PHOTOS] Downloaded {len(downloaded)} photos.")

    return downloaded_files(downloaded)
