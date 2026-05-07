import asyncio
from playwright.async_api import async_playwright

async def get_logo():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto('https://insuremep.com/', wait_until='networkidle')
        
        # The user uploaded a logo that says "InsureMEP Mechanical-Electrical-Plumbing"
        # It's likely an img or svg. Let's find all images.
        logo_element = await page.query_selector('img[alt*="logo" i], img[src*="logo" i], svg')
        
        if logo_element:
            await logo_element.screenshot(path='assets/logo.png')
            print("Logo successfully saved to assets/logo.png")
        else:
            print("Could not find logo element.")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(get_logo())
