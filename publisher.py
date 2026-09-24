import requests
import os
import time
from google import genai
from google.genai import types

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
                            print(f"[LOG] User selected topic {text}: {selection}", flush=True)
                            requests.post(
                                f"https://api.telegram.org/bot{bot_token}/sendMessage", 
                                json={"chat_id": chat_id, "text": f"✅ Confirmed. Crafting viral article and 3 cover variants...", "parse_mode": "Markdown"},
                                timeout=15
                            )
                            return selection
        except Exception:
            pass
        time.sleep(10)
        
    print("[LOG] 3-minute timeout reached. Auto-selecting Topic 1.", flush=True)
    requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json={"chat_id": chat_id, "text": "⏱️ *Timeout reached.* Auto-selecting Topic 1.", "parse_mode": "Markdown"}, timeout=15)
    return topics[0]

def send_telegram_imagen(bot_token, chat_id, prompt_text, caption):
    """Generates a flagship image via Google Imagen 3 and uploads it natively to Telegram."""
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    
    try:
        print(f"[LOG] Calling Google Imagen 3 API...", flush=True)
        result = client.models.generate_images(
            model='imagen-3.0-generate-002',
            prompt=prompt_text,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="16:9",
                person_generation="ALLOW_ADULT",
                output_mime_type="image/jpeg"
            )
        )
        
        image_bytes = result.generated_images[0].image.image_bytes
        image_path = "cover_image.jpg"
        
        with open(image_path, "wb") as f:
            f.write(image_bytes)
            
        print("[LOG] Imagen 3 photo generated. Uploading to Telegram...", flush=True)
        url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
        
        with open(image_path, "rb") as photo:
            payload = {"chat_id": chat_id, "caption": caption[:1024], "parse_mode": "Markdown"}
            res = requests.post(url, data=payload, files={"photo": photo}, timeout=30)
            
            if res.status_code != 200:
                payload["parse_mode"] = ""
                photo.seek(0)
                res = requests.post(url, data=payload, files={"photo": photo}, timeout=30)
                
        print(f"[TELEGRAM PHOTO STATUS] HTTP {res.status_code}", flush=True)
        
    except Exception as e:
        print(f"[ERROR] Failed to generate or send Imagen photo: {e}", flush=True)

def push_curated_to_telegram(title, body, image_prompts):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not bot_token or not chat_id:
        raise ValueError("CRITICAL: Telegram credentials missing!")

    print("\n[LOG] Generating and dispatching 3 distinct Cover Image options...", flush=True)
    for idx, prompt_text in enumerate(image_prompts, 1):
        caption = f"🎨 *COVER OPTION {idx} — IMAGEN 3*\n\n*Prompt:* _{prompt_text}_"
        send_telegram_imagen(bot_token, chat_id, prompt_text, caption)
        time.sleep(2)

    print("\n[LOG] Dispatching final curated article text...", flush=True)
    article_text = f"**{title}**\n\n{body}"
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    MAX_LENGTH = 3800
    chunks = []
    current_chunk = ""
    
    for paragraph in article_text.split('\n'):
        if len(current_chunk) + len(paragraph) + 1 > MAX_LENGTH:
            chunks.append(current_chunk.strip())
            current_chunk = paragraph + "\n"
        else:
            current_chunk += paragraph + "\n"
            
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
        
    total_parts = len(chunks)
    for idx, chunk in enumerate(chunks, 1):
        payload = {"chat_id": chat_id, "text": chunk, "parse_mode": "Markdown"}
        res = requests.post(url, json=payload, timeout=15)
        
        if res.status_code != 200:
            payload["parse_mode"] = ""
            res = requests.post(url, json=payload, timeout=15)
            
        print(f"[TELEGRAM TEXT STATUS] Part {idx}/{total_parts}: HTTP {res.status_code}", flush=True)
        time.sleep(1)
