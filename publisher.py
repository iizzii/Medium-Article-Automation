import requests
import os
import time
import urllib.parse

def send_telegram_photo(bot_token, chat_id, image_url, caption):
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    payload = {
        "chat_id": chat_id,
        "photo": image_url,
        "caption": caption,
        "parse_mode": "Markdown"
    }
    response = requests.post(url, json=payload)
    return response.status_code == 200

def send_telegram_text_chunks(bot_token, chat_id, text):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    MAX_LENGTH = 3900
    chunks = []
    current_chunk = ""
    
    for paragraph in text.split('\n'):
        if len(current_chunk) + len(paragraph) + 1 > MAX_LENGTH:
            chunks.append(current_chunk)
            current_chunk = paragraph + "\n"
        else:
            current_chunk += paragraph + "\n"
            
    if current_chunk:
        chunks.append(current_chunk)
        
    for chunk in chunks:
        payload = {
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": "Markdown"
        }
        res = requests.post(url, json=payload)
        if res.status_code != 200:
            # Fallback if markdown parsing fails
            payload["parse_mode"] = ""
            requests.post(url, json=payload)
        time.sleep(1)

def push_options_to_telegram(drafts):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not bot_token or not chat_id:
        raise ValueError("CRITICAL: Telegram credentials missing!")

    total = len(drafts)
    print(f"Delivering {total} article options to Telegram...", flush=True)

    for item in drafts:
        num = item["option_num"]
        label = item["label"]
        title = item["title"]
        body = item["body"]

        print(f"Sending Option {num}/{total}...", flush=True)

        # 1. Generate an editorial concept image
        visual_prompt = (
            f"Editorial dark moody conceptual illustration representing {title}. "
            f"Cyberpunk corporate infrastructure, minimalist, atmospheric lighting, high contrast, clean, no text, no letters."
        )
        encoded_prompt = urllib.parse.quote(visual_prompt)
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1200&height=800&nologo=true"
        
        caption = f"🎨 *COVER IMAGE — OPTION {num}/{total}*\n_{label}_\n\n*Title:* {title}"
        send_telegram_photo(bot_token, chat_id, image_url, caption)
        time.sleep(2)

        # 2. Send Article Text
        formatted_article = f"━━━━━━━━━━━━━━━━━━━━\n📌 *OPTION {num}: {label.upper()}*\n━━━━━━━━━━━━━━━━━━━━\n\n# {title}\n\n{body}"
        send_telegram_text_chunks(bot_token, chat_id, formatted_article)
        time.sleep(3) # Pause before delivering the next option
