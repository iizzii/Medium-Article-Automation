from playwright.sync_api import sync_playwright
import json
import time
import os

def push_to_medium(title, body):
    print("Starting headless browser to publish to Medium...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True) 
        context = browser.new_context()
        
        cookie_data = os.environ.get("MEDIUM_COOKIES")
        if not cookie_data:
            raise ValueError("No MEDIUM_COOKIES found in environment!")
            
        cookies = json.loads(cookie_data)
        # Filter and inject cookies
        valid_cookies = [{"name": c["name"], "value": c["value"], "domain": c["domain"], "path": c["path"]} for c in cookies]
        context.add_cookies(valid_cookies)
        
        page = context.new_page()
        page.goto("https://medium.com/new-story", timeout=60000)
        time.sleep(5) 
        
        # Fill Title
        page.keyboard.type(title)
        page.keyboard.press("Enter")
        
        # Fill Body using clipboard paste simulation to preserve markdown
        page.evaluate(f"navigator.clipboard.writeText(`{body}`)")
        page.keyboard.down("Control")
        page.keyboard.press("v")
        page.keyboard.up("Control")
        
        print("Draft successfully pasted into Medium!")
        time.sleep(5) # Allow Medium's auto-save to trigger
        browser.close()
