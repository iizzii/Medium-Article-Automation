import requests
import os
import time
import urllib.parse

def push_to_medium(title, body):
    print("Generating and sending cover image...", flush=True)
    
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not bot_token or not chat_id:
        raise ValueError("CRITICAL: Telegram credentials missing!")
        
    # --- NEW: GENERATE & SEND IMAGE ---
    # We use Pollinations AI, a 100% free image generation API that requires no keys
    image_prompt = f"Professional editorial illustration for article titled: {title}. Corporate style, cinematic, highly detailed, no text."
    encoded_prompt = urllib.parse.quote(image_prompt)
    
    # 1200x800 is the perfect resolution for a Medium article header
    image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1200&height=800&nologo=true"
    
    photo_api_url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    photo_payload = {
        "chat_id": chat_id,
        "photo": image_url, # Telegram will fetch the image directly from this URL
        "caption": "🖼 *Generated Cover Image*\n\n_Save this to your device and upload it as the header in Medium._",
        "parse_mode": "Markdown"
    }
    
    photo_response = requests.post(photo_api_url, json=photo_payload)
    if photo_response.status_code == 200:
        print("Successfully sent cover image!", flush=True)
    else:
        print(f"Failed to send image: {photo_response.text}", flush=True)
        
    time.sleep(2) # Brief pause before sending the article text

    # --- EXISTING: CHUNK AND SEND TEXT ---
    print("Sending article text...", flush=True)
    text_api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    full_message = f"{title}\n\n{body}"
    MAX_LENGTH = 4000
    chunks = []
    current_chunk = ""
    
    for paragraph in full_message.split('\n'):
        if len(current_chunk) + len(paragraph) + 1 > MAX_LENGTH:
            chunks.append(current_chunk)
            current_chunk = paragraph + "\n"
        else:
            current_chunk += paragraph + "\n"
            
    if current_chunk:
        chunks.append(current_chunk)
        
    for i, chunk in enumerate(chunks):
        payload = {
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": "Markdown"
        }
        
        response = requests.post(text_api_url, json=payload)
        
        if response.status_code != 200:
            print(f"Markdown error on part {i+1}. Retrying as plain text...", flush=True)
            payload["parse_mode"] = "" 
            response = requests.post(text_api_url, json=payload)
            
            if response.status_code != 200:
                raise Exception(f"Failed to send text. Status: {response.status_code}, Response: {response.text}")
                
        print(f"Successfully sent part {i+1} of {len(chunks)}!", flush=True)
        time.sleep(1)
