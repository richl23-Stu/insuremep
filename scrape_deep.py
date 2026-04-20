from playwright.sync_api import sync_playwright
import time
import json

def scrape_page(page, url, filename_prefix, wait_for=None):
    page.goto(url)
    page.wait_for_load_state("networkidle", timeout=15000)
    if wait_for:
        try:
            page.wait_for_selector(wait_for, timeout=5000)
        except:
            pass
    page.wait_for_timeout(2000)
    page.screenshot(path=f"{filename_prefix}.png", full_page=True)
    html = page.content()
    with open(f"{filename_prefix}.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Captured: {filename_prefix}")
    return html

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    
    # --- LOGIN ---
    page.goto("https://obligations.criticalasset.tech/")
    page.wait_for_timeout(3000)
    page.locator("input[type='email']").first.fill("richl23@uci.edu")
    page.locator("input[type='password']").first.fill(".u7bchh7v7esA1!")
    page.locator("button[type='submit']").first.click()
    page.wait_for_load_state("networkidle", timeout=15000)
    page.wait_for_timeout(3000)
    page.screenshot(path="page_01_dashboard.png", full_page=True)
    print("Dashboard captured.")
    
    base_url = "https://obligations.criticalasset.tech"
    
    # --- CLICK Asset Catalog ---
    try:
        page.locator("text=Asset Catalog").first.click()
        page.wait_for_load_state("networkidle", timeout=12000)
        page.wait_for_timeout(2000)
        page.screenshot(path="page_02_asset_catalog.png", full_page=True)
        print("Asset Catalog captured.")
    except Exception as e:
        print("Asset Catalog error:", e)
    
    # --- Go back and click Asset Obligations ---
    try:
        page.go_back()
        page.wait_for_timeout(2000)
        page.locator("text=Asset Obligations").first.click()
        page.wait_for_load_state("networkidle", timeout=12000)
        page.wait_for_timeout(2000)
        page.screenshot(path="page_03_asset_obligations.png", full_page=True)
        print("Asset Obligations captured.")
    except Exception as e:
        print("Asset Obligations error:", e)

    # --- Go back and click Obligations Workbench ---
    try:
        page.go_back()
        page.wait_for_timeout(2000)
        page.locator("text=Obligations Workbench").first.click()
        page.wait_for_load_state("networkidle", timeout=12000)
        page.wait_for_timeout(2000)
        page.screenshot(path="page_04_obligations_workbench.png", full_page=True)
        print("Obligations Workbench captured.")
    except Exception as e:
        print("Obligations Workbench error:", e)

    # --- Go back and click Warranty Explorer ---
    try:
        page.go_back()
        page.wait_for_timeout(2000)
        page.locator("text=Warranty Explorer").first.click()
        page.wait_for_load_state("networkidle", timeout=12000)
        page.wait_for_timeout(2000)
        page.screenshot(path="page_05_warranty_explorer.png", full_page=True)
        print("Warranty Explorer captured.")
    except Exception as e:
        print("Warranty Explorer error:", e)

    # --- Go back and click Field Onboarding ---
    try:
        page.go_back()
        page.wait_for_timeout(2000)
        page.locator("text=Field Onboarding").first.click()
        page.wait_for_load_state("networkidle", timeout=12000)
        page.wait_for_timeout(2000)
        page.screenshot(path="page_06_field_onboarding.png", full_page=True)
        print("Field Onboarding captured.")
    except Exception as e:
        print("Field Onboarding error:", e)
        
    browser.close()
    print("Done scraping!")
