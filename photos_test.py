from playwright.sync_api import sync_playwright

URL = input("Enter Trade Me listing URL: ")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()

    print("[TRADE ME] Opening listing...")
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_timeout(5000)

    thumbnails = page.locator("img.tm-gallery-view__thumbnail")
    count = thumbnails.count()

    print(f"\nGallery thumbnails found: {count}")

    selected_images = []

    for i in range(min(count, 5)):
        src = thumbnails.nth(i).get_attribute("src")

        if not src:
            continue

        image_url = src.replace(
            "/photoserver/64x64m/",
            "/photoserver/full/"
        )

        if image_url not in selected_images:
            selected_images.append(image_url)

    print("\nFIRST 5 GALLERY IMAGES:")

    for i, src in enumerate(selected_images, 1):
        print(f"[PHOTO {i}] {src}")

    print(f"\nTotal selected: {len(selected_images)}")

    input("\nPress Enter to close...")

    browser.close()