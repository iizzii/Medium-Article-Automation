import requests
import os

def push_to_medium(title, body):
    print("Sending article to Make.com webhook...")
    
    webhook_url = os.environ.get("MAKE_WEBHOOK_URL")
    if not webhook_url:
        raise ValueError("CRITICAL: MAKE_WEBHOOK_URL missing from environment variables!")
        
    payload = {
        "title": title,
        "body": body
    }
    
    response = requests.post(webhook_url, json=payload)
    
    if response.status_code == 200:
        print("Successfully sent draft to Make.com!")
    else:
        raise Exception(f"Failed to send data. Status code: {response.status_code}, Response: {response.text}")
