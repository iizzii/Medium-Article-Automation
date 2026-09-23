from playwright.sync_api import sync_playwright
import json
import time
import os

def push_to_medium(title, body):
    print("Starting headless browser to publish to Medium...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True) 
        
        # 1. Disguise the bot as a normal Windows Chrome browser to bypass security blocks
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        cookie_data = os.environ.get("MEDIUM_COOKIES")
        cookies = json.loads(cookie_data)
        valid_cookies = [{"name": c["name"], "value": c["value"], "domain": c["domain"], "path": c["path"]} for c in cookies]
        context.add_cookies(valid_cookies)
        
        page = context.new_page()
        print("Navigating to editor...")
        page.goto("https://medium.com/new-story", timeout=60000, wait_until="networkidle")
        
        # 2. Strict Login Check: Did we actually make it to the editor?
        print(f"Current URL: {page.url}")
        if "new-story" not in page.url:
            raise Exception("CRITICAL ERROR: Medium rejected the cookies and redirected us. Your session expired. You MUST export fresh cookies from your browser and update the MEDIUM_COOKIES secret in GitHub!")
        
        print("Waiting for editor to load...")
        # 3. Use the universal HTML attribute for rich-text editors
        page.wait_for_selector("[contenteditable='true']", timeout=15000)
        
        print("Targeting the Title field...")
        editor = page.locator("[contenteditable='true']").first
        editor.click()
        
        print("Inserting Title...")
        page.keyboard.insert_text(title)
        page.keyboard.press("Enter")
        time.sleep(2) 
        
        print("Inserting Body...")
        page.keyboard.insert_text(body)
        
        print("Waiting 15 seconds for Medium to auto-save to cloud...")
        time.sleep(15) 
        
        print("Draft successfully injected and saved!")
        browser.close()
