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
    
    # 1. Prepare the text safely
    clean_title = title.replace('#', '').replace('*', '').strip()
    raw_article = f"<b>{clean_title}</b>\n\n{body}"
    
    # Failsafe: Ensure any markdown asterisks are forced into HTML tags
    html_body_text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', raw_article)
    
    # 2. Send the Chat Preview (Chunked for Telegram limits)
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    MAX_LENGTH = 3800
    chunks = []
    current_chunk = ""
    
    for paragraph in html_body_text.split('\n'):
        if len(current_chunk) + len(paragraph) + 1 > MAX_LENGTH:
            chunks.append(current_chunk.strip())
            current_chunk = paragraph + "\n"
        else:
            current_chunk += paragraph + "\n"
            
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
        
    for idx, chunk in enumerate(chunks, 1):
        payload = {"chat_id": chat_id, "text": chunk, "parse_mode": "HTML"}
        res = requests.post(url, json=payload, timeout=15)
        if res.status_code != 200:
            payload["parse_mode"] = ""
            requests.post(url, json=payload, timeout=15)
        time.sleep(1)

    # 3. Send the Tags
    tag_msg = f"🏷️ <b>Suggested Medium Tags:</b>\n\n{tags}"
    requests.post(url, json={"chat_id": chat_id, "text": tag_msg, "parse_mode": "HTML"}, timeout=15)

    # ==========================================
    # 4. GENERATE & SEND THE MEDIUM HTML DRAFT
    # ==========================================
    print("\n[LOG] Dispatching Medium-ready Rich Text file...", flush=True)
    
    # Convert newline breaks into proper HTML paragraphs
    formatted_html_body = html_body_text.replace('\n\n', '</p><p>').replace('\n', '<br>')
    
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{clean_title}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; max-width: 700px; margin: 40px auto; padding: 0 20px; color: #292929; }}
        h1 {{ font-size: 32px; font-weight: bold; margin-bottom: 20px; }}
        p {{ font-size: 20px; margin-bottom: 24px; }}
        b, strong {{ font-weight: bold; color: #000; }}
    </style>
</head>
<body>
    <p>{formatted_html_body}</p>
</body>
</html>"""

    # Save the file locally on the runner
    file_name = "Medium_Draft.html"
    with open(file_name, "w", encoding="utf-8") as f:
        f.write(html_content)

    # Upload the file to Telegram
    doc_url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    with open(file_name, "rb") as doc:
        caption_text = "📝 <b>MEDIUM DRAFT READY</b>\n\nOpen this file in your browser, press <b>Select All -> Copy</b>, and paste directly into Medium. Your bold formatting will transfer perfectly!"
        payload = {"chat_id": chat_id, "caption": caption_text, "parse_mode": "HTML"}
        requests.post(doc_url, data=payload, files={"document": doc})
