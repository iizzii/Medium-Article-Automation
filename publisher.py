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
        cookies = json.loads(cookie_data)
        valid_cookies = [{"name": c["name"], "value": c["value"], "domain": c["domain"], "path": c["path"]} for c in cookies]
        context.add_cookies(valid_cookies)
        
        page = context.new_page()
        print("Navigating to editor...")
        page.goto("https://medium.com/new-story", timeout=60000)
        
        # Wait for Medium's editor textboxes to fully render
        print("Waiting for editor to load...")
        page.wait_for_selector("role=textbox", timeout=15000)
        
        print("Targeting the Title field...")
        # explicitly click the first textbox (the Title)
        editor = page.locator("role=textbox").first
        editor.click()
        
        print("Inserting Title...")
        # insert_text injects the string safely without needing Ctrl+V
        page.keyboard.insert_text(title)
        page.keyboard.press("Enter")
        time.sleep(1) # Give Medium a second to create the new paragraph block
        
        print("Inserting Body...")
        page.keyboard.insert_text(body)
        
        print("Waiting 15 seconds for Medium to auto-save to cloud...")
        time.sleep(15) 
        
        print("Draft successfully injected and saved!")
        browser.close()
