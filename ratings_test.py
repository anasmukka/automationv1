from playwright.sync_api import sync_playwright


TRADE_ME_URL = "https://www.trademe.co.nz/a/motors/cars/mazda/demio/listing/6095666144"


def run():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        page = browser.new_page()

        print("[TRADE ME] Opening listing...")
        page.goto(TRADE_ME_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(4000)

        ratings = page.locator(
            'div.tm-listing-rating-star__blue[aria-label]'
        )

        print(f"\nActual rating elements: {ratings.count()}\n")

        for i in range(ratings.count()):
            rating = ratings.nth(i)

            aria = rating.get_attribute("aria-label")

            print(f"[RATING {i + 1}] {aria}")

        print("\nPress Enter to close...")
        input()

        browser.close()


if __name__ == "__main__":
    run()