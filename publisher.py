import requests
import os
import time
import urllib.parse
import random

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
    
    msg = "📰 *Today's Top 5 Trending Topics:*\n\n"
    for i, t in enumerate(topics, 1):
        msg += f"{i}. {t}\n\n"
    msg += "_Reply with a number (1-5) within the next 3 minutes._"
    
    print("[LOG] Sending menu to Telegram. Waiting 3 minutes for response...", flush=True)
    requests.post(
        f"https://api.telegram.org/bot{bot_token}/sendMessage", 
        json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"},
        timeout=15
    )
    
    last_update_id = get_latest_update_id(bot_token)
    offset = last_update_id + 1 if last_update_id else None
    
    for _ in range(18): 
        url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
        if offset: 
            url += f"?offset={offset}"
        
        try:
            res = requests.get(url, timeout=10).json()
            if res.get("ok") and res["result"]:
                for update in res["result"]:
                    offset = update["update_id"] + 1
                    if "message" in update and "text" in update["message"]:
                        text = update["message"]["text"].strip()
                        if text.isdigit() and 1 <= int(text) <= 5:
                            selection = topics[int(text)-1]
                            print(f"[LOG] User selected topic {text}: {selection}", flush=True)
                            requests.post(
                                f"https://api.telegram.org/bot{bot_token}/sendMessage", 
                                json={"chat_id": chat_id, "text": f"✅ Confirmed. Generating 3 angles for:\n*{selection}*", "parse_mode": "Markdown"},
                                timeout=15
                            )
                            return selection
        except Exception:
            pass
        time.sleep(10)
        
    print("[LOG] 3-minute timeout reached. Auto-selecting Topic 1.", flush=True)
    requests.post(
        f"https://api.telegram.org/bot{bot_token}/sendMessage", 
        json={"chat_id": chat_id, "text": "⏱️ *Timeout reached.* Auto-selecting Topic 1.", "parse_mode": "Markdown"},
        timeout=15
    )
    return topics[0]

def send_telegram_photo(bot_token, chat_id, image_url, caption):
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    payload = {
        "chat_id": chat_id, 
        "photo": image_url, 
        "caption": caption[:1024], # Telegram photo captions max at 1024 chars
        "parse_mode": "Markdown"
    }
    res = requests.post(url, json=payload, timeout=30)
    if res.status_code != 200:
        # Retry with plain text caption if markdown formatting triggers an error
        payload["parse_mode"] = ""
        res = requests.post(url, json=payload, timeout=30)
    print(f"[TELEGRAM PHOTO STATUS] Code {res.status_code}", flush=True)

def send_telegram_text_chunks(bot_token, chat_id, full_text):
    """Splits articles exceeding 3,800 characters into safe chunks at paragraph breaks."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    MAX_LENGTH = 3800
    chunks = []
    current_chunk = ""
    
    for paragraph in full_text.split('\n'):
        if len(current_chunk) + len(paragraph) + 1 > MAX_LENGTH:
            chunks.append(current_chunk.strip())
            current_chunk = paragraph + "\n"
        else:
            current_chunk += paragraph + "\n"
            
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
        
    total_parts = len(chunks)
    for idx, chunk in enumerate(chunks, 1):
        payload = {
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": "Markdown"
        }
        res = requests.post(url, json=payload, timeout=15)
        
        # If Telegram rejects markdown formatting (e.g. unclosed asterisks), retry as plain text
        if res.status_code != 200:
            print(f"[WARN] Markdown delivery failed for part {idx}/{total_parts}. Retrying as raw text...", flush=True)
            payload["parse_mode"] = ""
            res = requests.post(url, json=payload, timeout=15)
            
        print(f"[TELEGRAM TEXT STATUS] Part {idx}/{total_parts}: HTTP {res.status_code}", flush=True)
        if res.status_code != 200:
            print(f"[ERROR RESPONSE] {res.text}", flush=True)
            
        time.sleep(1)

def push_options_to_telegram(drafts):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not bot_token or not chat_id:
        raise ValueError("CRITICAL: Telegram credentials missing from environment variables!")

    # 3 distinct open-source generation models
    image_models = ["flux", "turbo", "realism"]

    for item in drafts:
        num = item["option_num"]
        label = item["label"]
        print(f"\n[LOG] Processing Option {num}: {label}", flush=True)
        
        encoded_prompt = urllib.parse.quote(item["image_prompt"])
        
        # 1. Send the 3 image variations
        for model_name in image_models:
            seed = random.randint(1, 999999)
            image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?model={model_name}&width=1200&height=800&nologo=true&seed={seed}"
            
            caption = f"🎨 *OPTION {num} — IMAGE ({model_name.upper()})*\n\n*Prompt:* _{item['image_prompt']}_"
            print(f"[LOG] Dispatching image from model: {model_name.upper()}", flush=True)
            send_telegram_photo(bot_token, chat_id, image_url, caption)
            time.sleep(2)

        # 2. Send the article text safely chunked
        print(f"[LOG] Dispatching text for Option {num}...", flush=True)
        
        # Clean article text ready for copy-pasting directly into Medium
        article_text = f"**{item['title']}**\n\n{item['body']}"
        send_telegram_text_chunks(bot_token, chat_id, article_text)
        time.sleep(2)
