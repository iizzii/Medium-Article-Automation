import requests
import os
import time
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
    
    msg = "📰 <b>Today's Top 10 Tech Topics:</b>\n\n"
    for i, t in enumerate(topics, 1):
        msg += f"{i}. {t}\n"
    msg += "\n<i>Reply with a number (1-10) within the next 3 minutes.</i>"
    
    requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"})
    
    last_update_id = get_latest_update_id(bot_token)
    offset = last_update_id + 1 if last_update_id else None
    
    print("[LOG] Waiting 3 minutes for user selection on Telegram...", flush=True)
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
                        if text.isdigit() and 1 <= int(text) <= 10:
                            selection = topics[int(text)-1]
                            requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json={"chat_id": chat_id, "text": f"✅ Confirmed. Crafting article for:\n<b>{selection}</b>", "parse_mode": "HTML"})
                            return selection
        except Exception:
            pass
        time.sleep(10)
        
    print("[LOG] Timeout reached. Auto-selecting Topic 1.", flush=True)
    requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json={"chat_id": chat_id, "text": "⏱️ <i>Timeout reached. Auto-selecting Topic 1.</i>", "parse_mode": "HTML"})
    return topics[0]

def push_article_to_telegram(title, body, tags):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not bot_token or not chat_id:
        raise ValueError("CRITICAL: Telegram credentials missing!")

    print("\n[LOG] Formatting and dispatching article...", flush=True)
    
    # Prepend the title boldly
    raw_article = f"<b>{title}</b>\n\n{body}"
    
    # Failsafe: If the AI hallucinates **markdown**, force it into <b>HTML</b>
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
        
    # 1. Send the Article Chunks
    for idx, chunk in enumerate(chunks, 1):
        payload = {"chat_id": chat_id, "text": chunk, "parse_mode": "HTML"}
        res = requests.post(url, json=payload, timeout=15)
        
        if res.status_code != 200:
            payload["parse_mode"] = ""
            res = requests.post(url, json=payload, timeout=15)
            
        print(f"[TELEGRAM TEXT STATUS] Part {idx}/{len(chunks)}: HTTP {res.status_code}", flush=True)
        time.sleep(1)

    # 2. Send the Hashtags as a distinct follow-up message
    print("\n[LOG] Dispatching Medium tags...", flush=True)
    tag_msg = f"🏷️ <b>Suggested Medium Tags:</b>\n\n{tags}"
    requests.post(url, json={"chat_id": chat_id, "text": tag_msg, "parse_mode": "HTML"}, timeout=15)
