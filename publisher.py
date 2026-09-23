from playwright.sync_api import sync_playwright
import json
import time
import os

def push_to_medium(title, body):
    print("Starting headless browser to publish to Medium...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True) 
        
        # Force a standard laptop screen size so coordinates are predictable
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )
        
        cookie_data = os.environ.get("MEDIUM_COOKIES")
        cookies = json.loads(cookie_data)
        valid_cookies = [{"name": c["name"], "value": c["value"], "domain": c["domain"], "path": c["path"]} for c in cookies]
        context.add_cookies(valid_cookies)
        
        page = context.new_page()
        print("Navigating to editor...")
        page.goto("https://medium.com/new-story", timeout=60000)
        time.sleep(10) # Let everything load
        
        # Take a picture of what the bot sees when it loads
        page.screenshot(path="debug1_load.png")
        print("Screenshot 1 saved.")
        
        # Mash ESCAPE to aggressively close any banners or popups
        page.keyboard.press("Escape")
        page.keyboard.press("Escape")
        time.sleep(2)
        
        # Click exactly where the title box sits on a 1280x720 screen
        page.mouse.click(300, 250)
        time.sleep(1)
        
        print("Inserting Title & Body...")
        page.keyboard.insert_text(title)
        page.keyboard.press("Enter")
        time.sleep(2) 
        page.keyboard.insert_text(body)
        
        # Take a picture of what it looks like after typing
        time.sleep(3)
        page.screenshot(path="debug2_typed.png")
        print("Screenshot 2 saved.")
        
        print("Waiting 15 seconds for Medium to auto-save...")
        time.sleep(15) 
        browser.close()
