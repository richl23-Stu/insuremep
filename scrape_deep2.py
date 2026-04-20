from playwright.sync_api import sync_playwright

BASE = "https://obligations.criticalasset.tech"

def login(page):
    page.goto(BASE)
    page.wait_for_timeout(3000)
    page.locator("input[type='email']").first.fill("richl23@uci.edu")
    page.locator("input[type='password']").first.fill(".u7bchh7v7esA1!")
    page.locator("button[type='submit']").first.click()
    page.wait_for_load_state("networkidle", timeout=15000)
    page.wait_for_timeout(3000)
    print("Logged in.")

def capture(page, filename, extra_wait=3000):
    page.wait_for_load_state("networkidle", timeout=15000)
    page.wait_for_timeout(extra_wait)
    page.screenshot(path=filename, full_page=True)
    print(f"Captured: {filename}")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    login(page)
    
    # --- 1. Asset Obligations ---
    try:
        page.goto(BASE)
        page.wait_for_timeout(2000)
        page.locator("text=Asset Obligations").first.click()
        capture(page, "page_03_asset_obligations.png")
    except Exception as e:
        print("Asset Obligations error:", e)
        page.screenshot(path="page_03_error.png")
    
    # --- 2. Obligations Workbench ---
    try:
        page.goto(BASE)
        page.wait_for_timeout(2000)
        page.locator("text=Obligations Workbench").first.click()
        capture(page, "page_04_obligations_workbench.png")
    except Exception as e:
        print("Obligations Workbench error:", e)
        page.screenshot(path="page_04_error.png")
    
    # --- 3. Warranty Explorer ---
    try:
        page.goto(BASE)
        page.wait_for_timeout(2000)
        page.locator("text=Warranty Explorer").first.click()
        capture(page, "page_05_warranty_explorer.png")
    except Exception as e:
        print("Warranty Explorer error:", e)
        page.screenshot(path="page_05_error.png")
    
    # --- 4. Field Onboarding ---
    try:
        page.goto(BASE)
        page.wait_for_timeout(2000)
        page.locator("text=Field Onboarding").first.click()
        capture(page, "page_06_field_onboarding.png")
    except Exception as e:
        print("Field Onboarding error:", e)
        page.screenshot(path="page_06_error.png")
    
    # --- 5. Drill into HVAC in Asset Catalog ---
    try:
        page.goto(BASE)
        page.wait_for_timeout(2000)
        page.locator("text=Asset Catalog").first.click()
        page.wait_for_load_state("networkidle", timeout=10000)
        page.wait_for_timeout(2000)
        page.locator("text=HVAC").first.click()
        capture(page, "page_07_hvac_detail.png", extra_wait=4000)
    except Exception as e:
        print("HVAC detail error:", e)
        page.screenshot(path="page_07_error.png")

    browser.close()
    print("Done!")
