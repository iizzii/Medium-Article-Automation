import requests
import os
import time
import urllib.parse
import random

def get_latest_update_id(bot_token):
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
    try:
        res = requests.get(url).json()
        if res.get("ok") and res["result"]:
            return res["result"][-1]["update_id"]
    except:
        pass
    return None

def wait_for_user_selection(topics):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    msg = "📰 *Today's Top 5 Trending Topics:*\n\n"
    for i, t in enumerate(topics, 1):
        msg += f"{i}. {t}\n\n"
    msg += "_Reply with a number (1-5) within the next 3 minutes._"
    
    print("[LOG] Sending menu to Telegram. Waiting 3 minutes...", flush=True)
    requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"})
    
    last_update_id = get_latest_update_id(bot_token)
    offset = last_update_id + 1 if last_update_id else None
    
    for i in range(18): 
        url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
        if offset: url += f"?offset={offset}"
        
        try:
            res = requests.get(url).json()
            if res.get("ok") and res["result"]:
                for update in res["result"]:
                    offset = update["update_id"] + 1
                    if "message" in update and "text" in update["message"]:
                        text = update["message"]["text"].strip()
                        if text.isdigit() and 1 <= int(text) <= 5:
                            selection = topics[int(text)-1]
                            print(f"[LOG] User selected topic {text} via Telegram.", flush=True)
                            requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json={"chat_id": chat_id, "text": f"✅ Confirmed. Generating 3 angles for:\n*{selection}*", "parse_mode": "Markdown"})
                            return selection
        except:
            pass
        time.sleep(10)
        
    print("[LOG] 3-minute timeout reached. Auto-selecting Topic 1.", flush=True)
    requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json={"chat_id": chat_id, "text": "⏱️ *Timeout reached.* Auto-selecting Topic 1.", "parse_mode": "Markdown"})
    return topics[0]

def send_telegram_photo(bot_token, chat_id, image_url, caption):
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    payload = {"chat_id": chat_id, "photo": image_url, "caption": caption, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

def push_options_to_telegram(drafts):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    for item in drafts:
        print(f"\n[LOG] Processing Telegram delivery for Option {item['option_num']}", flush=True)
        
        # We explicitly force the FLUX model, which fixes the "sad/bad" image quality issue
        # We also generate 2 distinct images using different random seeds so you have options
        encoded_prompt = urllib.parse.quote(item["image_prompt"])
        
        for variant in range(1, 3):
            seed = random.randint(1, 999999)
            image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?model=flux&width=1200&height=800&nologo=true&seed={seed}"
            
            caption = f"🎨 *OPTION {item['option_num']} - COVER IMAGE {variant}*\n_Model: FLUX.1 | Seed: {seed}_\n\n*Prompt Used:* {item['image_prompt']}"
            print(f"[LOG] Sending Image Variant {variant} with seed {seed}", flush=True)
            send_telegram_photo(bot_token, chat_id, image_url, caption)
            time.sleep(3)

        print(f"[LOG] Sending full article text for Option {item['option_num']}:\n\n{item['body']}\n", flush=True)
        
        # Send the raw, copy-paste ready article body
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {"chat_id": chat_id, "text": f"{item['title']}\n\n{item['body']}"} # Raw text, no markdown parser strictly enforced
        
        try:
            requests.post(url, json=payload)
        except Exception as e:
            print(f"[ERROR] Failed to send article text: {e}", flush=True)
            
        time.sleep(4)
