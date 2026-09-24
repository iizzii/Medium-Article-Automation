import requests
import os
import time
import urllib.parse

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
    
    # 1. Send the menu to Telegram
    msg = "📰 *Today's Top 5 Trending Topics:*\n\n"
    for i, t in enumerate(topics, 1):
        msg += f"{i}. {t}\n\n"
    msg += "_Reply with a number (1-5) within the next 10 minutes._"
    
    requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"})
    
    # 2. Wait for user reply (polls every 10 seconds for 10 mins)
    last_update_id = get_latest_update_id(bot_token)
    offset = last_update_id + 1 if last_update_id else None
    
    print("Waiting 10 minutes for user reply on Telegram...", flush=True)
    for _ in range(60): 
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
                            confirm_msg = f"✅ Got it! Generating 3 angles for:\n*{selection}*\n\n_Please wait ~2 minutes..._"
                            requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json={"chat_id": chat_id, "text": confirm_msg, "parse_mode": "Markdown"})
                            return selection
        except:
            pass
        time.sleep(10)
        
    requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json={"chat_id": chat_id, "text": "⏱️ Time's up! Auto-selecting Topic #1."})
    return topics[0]

def send_telegram_photo(bot_token, chat_id, image_url, caption):
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    payload = {"chat_id": chat_id, "photo": image_url, "caption": caption, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

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
            
    if current_chunk: chunks.append(current_chunk)
        
    for chunk in chunks:
        payload = {"chat_id": chat_id, "text": chunk, "parse_mode": "Markdown"}
        res = requests.post(url, json=payload)
        if res.status_code != 200:
            payload["parse_mode"] = ""
            requests.post(url, json=payload)
        time.sleep(1)

def push_options_to_telegram(drafts):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    total = len(drafts)

    for item in drafts:
        num = item["option_num"]
        title = item["title"]
        body = item["body"]

        # BRIGHT, PROFESSIONAL IMAGE PROMPT
        visual_prompt = f"Bright modern corporate technology office, abstract cybersecurity data visualization, vibrant, optimistic, highly detailed professional editorial photography representing {title}. Clean, 8k resolution, no text, no letters, no watermarks."
        encoded_prompt = urllib.parse.quote(visual_prompt)
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1200&height=800&nologo=true"
        
        # Send intro/image
        caption = f"📌 *OPTION {num}: {item['label']}*\n\n_Download this image for the Medium header._"
        send_telegram_photo(bot_token, chat_id, image_url, caption)
        time.sleep(2)

        # Send clean, Medium-ready article (No bot labels in this message, pure copy-paste)
        formatted_article = f"{title}\n\n{body}"
        send_telegram_text_chunks(bot_token, chat_id, formatted_article)
        time.sleep(3)
