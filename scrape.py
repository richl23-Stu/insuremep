from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://obligations.criticalasset.tech/")
    
    # Wait for the login page to somewhat load
    page.wait_for_timeout(3000)
    page.screenshot(path="01_login_page.png", full_page=True)
    
    try:
        # Email input
        email_input = page.locator("input[type='email']")
        if email_input.count() > 0:
            email_input.first.fill("richl23@uci.edu")
        else:
            page.locator("input[name*='email' i], input[id*='email' i]").first.fill("richl23@uci.edu")
            
        # Password
        pwd_input = page.locator("input[type='password']")
        if pwd_input.count() > 0:
            pwd_input.first.fill(".u7bchh7v7esA1!")
        else:
            page.locator("input[name*='password' i], input[id*='password' i]").first.fill(".u7bchh7v7esA1!")
            
        page.screenshot(path="02_filled_login.png")
        
        # Submit
        submit_btn = page.locator("button[type='submit']")
        if submit_btn.count() > 0:
            submit_btn.first.click()
        else:
            # try clicking any button that says submit or login
            page.locator("button, input[type='submit']").filter(has_text="Log").first.click()
            
        print("Clicked login, waiting for network idle...")
        page.wait_for_load_state("networkidle", timeout=15000)
        page.wait_for_timeout(3000)  # Give JS frameworks extra time to render the dashboard
        
        page.screenshot(path="03_dashboard.png", full_page=True)
        
        html = page.content()
        with open("04_dashboard.html", "w", encoding="utf-8") as f:
            f.write(html)
            
        print("Successfully captured dashboard!")
        
    except Exception as e:
        print("Error during login or screenshot:", e)
        page.screenshot(path="05_error.png")
    finally:
        browser.close()
