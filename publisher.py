import requests
import os
import time

def push_to_medium(title, body):
    print("Sending article directly to Telegram...", flush=True)
    
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not bot_token or not chat_id:
        raise ValueError("CRITICAL: Telegram credentials missing!")
        
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    # Format the complete message
    full_message = f"{title}\n\n{body}"
    
    # Telegram's character limit is 4096. We will split at 4000 to be safe.
    MAX_LENGTH = 4000
    chunks = []
    current_chunk = ""
    
    # Split safely by paragraphs to avoid breaking Markdown tags in half
    for paragraph in full_message.split('\n'):
        if len(current_chunk) + len(paragraph) + 1 > MAX_LENGTH:
            chunks.append(current_chunk)
            current_chunk = paragraph + "\n"
        else:
            current_chunk += paragraph + "\n"
            
    if current_chunk:
        chunks.append(current_chunk)
        
    # Send chunks sequentially
    for i, chunk in enumerate(chunks):
        payload = {
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": "Markdown"
        }
        
        response = requests.post(url, json=payload)
        
        # If Telegram rejects the Markdown (e.g., an unclosed bold tag across chunks), send as plain text
        if response.status_code != 200:
            print(f"Markdown error on part {i+1}. Retrying as plain text...", flush=True)
            payload["parse_mode"] = "" 
            response = requests.post(url, json=payload)
            
            if response.status_code != 200:
                raise Exception(f"Failed to send data. Status code: {response.status_code}, Response: {response.text}")
                
        print(f"Successfully sent part {i+1} of {len(chunks)} to Telegram!", flush=True)
        time.sleep(1) # Wait 1 second so messages arrive in the correct order
