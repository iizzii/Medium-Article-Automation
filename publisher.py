import requests
import os
import time
import urllib.parse
import random
import re

def get_latest_update_id(bot_token):
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
    try:
        res = requests.get(url, timeout=10).json()
        if res.get("ok") and res["result"]:
            return res["result"][-1]["update_id"]
    except Exception:
        pass
    return None

def wait_for_user_selection(topics):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    msg = "📰 <b>Today's Top 5 Trending Topics:</b>\n\n"
    for i, t in enumerate(topics, 1):
        msg += f"{i}. {t}\n\n"
    msg += "<i>Reply with a number (1-5) within the next 3 minutes.</i>"
    
    requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"})
    
    last_update_id = get_latest_update_id(bot_token)
    offset = last_update_id + 1 if last_update_id else None
    
    for _ in range(18): 
        url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
        if offset: url += f"?offset={offset}"
        
        try:
            res = requests.get(url, timeout=10).json()
            if res.get("ok") and res["result"]:
                for update in res["result"]:
                    offset = update["update_id"] + 1
                    if "message" in update and "text" in update["message"]:
                        text = update["message"]["text"].strip()
                        if text.isdigit() and 1 <= int(text) <= 5:
                            selection = topics[int(text)-1]
                            requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json={"chat_id": chat_id, "text": f"✅ Confirmed. Crafting viral article and covers for:\n<b>{selection}</b>", "parse_mode": "HTML"})
                            return selection
        except Exception:
            pass
        time.sleep(10)
        
    requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json={"chat_id": chat_id, "text": "⏱️ <i>Timeout reached. Auto-selecting Topic 1.</i>", "parse_mode": "HTML"})
    return topics[0]

def query_pollinations(prompt_text, model_name):
    """Hits the free Pollinations API using specific premium models and random seeds."""
    encoded_prompt = urllib.parse.quote(prompt_text)
    seed = random.randint(1, 9999999)
    # Using 1200x800 for perfect Medium 16:9 header size, bypassing cache with enhance=true
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1200&height=800&nologo=true&model={model_name}&seed={seed}&enhance=true"
    
    for attempt in range(3):
        try:
            print(f"[LOG] Fetching from Pollinations ({model_name}) - Attempt {attempt+1}/3...", flush=True)
            res = requests.get(url, timeout=60)
            if res.status_code == 200:
                return res.content
            time.sleep(5)
        except Exception as e:
            print(f"[ERROR] Network error: {e}", flush=True)
            time.sleep(5)
    return None

def send_telegram_photo_bytes(bot_token, chat_id, image_bytes, caption):
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    with open("temp_cover.jpg", "wb") as f:
        f.write(image_bytes)
        
    with open("temp_cover.jpg", "rb") as photo:
        payload = {"chat_id": chat_id, "caption": caption[:1024], "parse_mode": "HTML"}
        res = requests.post(url, data=payload, files={"photo": photo}, timeout=30)
    print(f"[TELEGRAM PHOTO STATUS] HTTP {res.status_code}", flush=True)

def push_curated_to_telegram(title, body, image_prompts):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not bot_token or not chat_id:
        raise ValueError("CRITICAL: Telegram credentials missing!")

    # 1. Generate and Send Images (3 Distinct Models via Pollinations)
    print("\n[LOG] Generating and dispatching 3 distinct Cover Image options...", flush=True)
    
    # We map the 3 image prompts to 3 distinct backend models
    models_to_use = [
        ("flux-realism", "FLUX Realism (Photorealistic)"),
        ("flux-3d", "FLUX 3D (Unreal Engine Style)"),
        ("flux", "FLUX Standard (Graphic/Editorial)")
    ]
    
    for idx, (prompt_text, (model_id, label)) in enumerate(zip(image_prompts, models_to_use), 1):
        image_bytes = query_pollinations(prompt_text, model_id)
        
        if image_bytes:
            caption = f"🎨 <b>COVER OPTION {idx} — {label}</b>\n\n<b>Prompt:</b> <i>{prompt_text}</i>"
            send_telegram_photo_bytes(bot_token, chat_id, image_bytes, caption)
        time.sleep(3)

    # 2. Format Text for Perfect Medium Copy-Pasting
    print("\n[LOG] Formatting and dispatching final curated article text...", flush=True)
    
    # Clean the title just in case the AI added its own markdown, then wrap it securely
    clean_title = title.replace('*', '').replace('#', '').strip()
    raw_article = f"**{clean_title}**\n\n{body}"
    
    # MAGIC FIX: Convert Markdown asterisks into strict HTML bold tags for Telegram
    # Telegram's Markdown parser fails easily. HTML <b> works 100% of the time.
    html_article = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', raw_article)
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    MAX_LENGTH = 3800
    chunks = []
    current_chunk = ""
    
    for paragraph in html_article.split('\n'):
        if len(current_chunk) + len(paragraph) + 1 > MAX_LENGTH:
            chunks.append(current_chunk.strip())
            current_chunk = paragraph + "\n"
        else:
            current_chunk += paragraph + "\n"
            
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
        
    total_parts = len(chunks)
    for idx, chunk in enumerate(chunks, 1):
        payload = {"chat_id": chat_id, "text": chunk, "parse_mode": "HTML"}
        res = requests.post(url, json=payload, timeout=15)
        
        if res.status_code != 200:
            # Fallback if HTML is somehow malformed
            payload["parse_mode"] = ""
            res = requests.post(url, json=payload, timeout=15)
            
        print(f"[TELEGRAM TEXT STATUS] Part {idx}/{total_parts}: HTTP {res.status_code}", flush=True)
        time.sleep(1)
