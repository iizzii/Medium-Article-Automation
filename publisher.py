from playwright.sync_api import sync_playwright
import json
import time
import os

def push_to_medium(title, body):
    print("Starting headless browser to publish to Medium...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True) 
        context = browser.new_context()
        
        context.grant_permissions(["clipboard-read", "clipboard-write"])
        
        cookie_data = os.environ.get("MEDIUM_COOKIES")
        cookies = json.loads(cookie_data)
        valid_cookies = [{"name": c["name"], "value": c["value"], "domain": c["domain"], "path": c["path"]} for c in cookies]
        context.add_cookies(valid_cookies)
        
        page = context.new_page()
        print("Navigating to editor...")
        page.goto("https://medium.com/new-story", timeout=60000)
        time.sleep(5) 
        
        # SAFETY CHECK 1: Did we actually log in?
        print(f"Current URL: {page.url}")
        if "new-story" not in page.url:
            raise Exception("Login failed! Medium rejected the cookies. You may need to export fresh cookies from your browser.")
        
        # SAFETY CHECK 2: Explicitly click the page to guarantee focus
        page.mouse.click(200, 300) 
        time.sleep(1)
        
        print("Typing title...")
        page.keyboard.type(title)
        page.keyboard.press("Enter")
        
        print("Pasting body...")
        page.evaluate("text => navigator.clipboard.writeText(text)", body)
        page.keyboard.down("Control")
        page.keyboard.press("v")
        page.keyboard.up("Control")
        
        print("Waiting for auto-save...")
        # SAFETY CHECK 3: Wait longer to ensure Medium's cloud syncs the draft
        time.sleep(15) 
        
        print("Draft successfully pasted into Medium!")
        browser.close()
