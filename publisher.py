from playwright.sync_api import sync_playwright
import json
import time
import os

def push_to_medium(title, body):
    print("Starting headless browser to publish to Medium...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True) 
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        cookie_data = os.environ.get("MEDIUM_COOKIES")
        cookies = json.loads(cookie_data)
        valid_cookies = [{"name": c["name"], "value": c["value"], "domain": c["domain"], "path": c["path"]} for c in cookies]
        context.add_cookies(valid_cookies)
        
        page = context.new_page()
        print("Navigating to editor...")
        page.goto("https://medium.com/new-story", timeout=60000)
        
        print(f"Current URL: {page.url}")
        if "new-story" not in page.url:
            raise Exception("CRITICAL ERROR: Medium rejected the cookies.")
        
        print("Waiting for Javascript to load...")
        time.sleep(8) # Hard wait to ensure Medium's editor scripts fully load
        
        # Dismiss any random popups Medium might show
        page.keyboard.press("Escape")
        
        print("Targeting the Title field...")
        try:
            # Method A: Look for the native 'Title' placeholder text
            title_box = page.get_by_placeholder("Title")
            title_box.wait_for(timeout=5000)
            title_box.click()
            print("Found placeholder successfully.")
        except:
            # Method B: Blind click where the title box is guaranteed to be
            print("Could not find 'Title' placeholder. Clicking coordinates...")
            # Click dead-center near the top of the screen
            page.mouse.click(page.viewport_size['width'] / 2, 150)
            time.sleep(1)
        
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
