import requests
import os

def push_to_medium(title, body):
    print("Sending article directly to Telegram...")
    
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not bot_token or not chat_id:
        raise ValueError("CRITICAL: Telegram credentials missing!")
        
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    message = f"{title}\n\n{body}"
    
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown" # Tells Telegram to format your headers and bullets
    }
    
    response = requests.post(url, json=payload)
    
    if response.status_code == 200:
        print("Successfully sent draft to Telegram!")
    else:
        raise Exception(f"Failed to send data. Status code: {response.status_code}, Response: {response.text}")
