import requests
import os
import time
import urllib.parse

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
    
    print("[LOG] Sending menu to Telegram. Waiting 3 minutes...", flush=True)
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
                                json={"chat_id": chat_id, "text": f"✅ Confirmed. Crafting viral article and 3 cover variants...", "parse_mode": "Markdown"}
                            )
                            return selection
        except Exception:
            pass
        time.sleep(10)
        
    print("[LOG] 3-minute timeout reached. Auto-selecting Topic 1.", flush=True)
    requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json={"chat_id": chat_id, "text": "⏱️ *Timeout reached.* Auto-selecting Topic 1.", "parse_mode": "Markdown"})
    return topics[0]

def query_huggingface(model_id, prompt_text, hf_token):
    """Hits the Hugging Face Serverless API and downloads the image bytes, with robust error handling."""
    url = f"https://api-inference.huggingface.co/models/{model_id}"
    headers = {"Authorization": f"Bearer {hf_token}"}
    payload = {"inputs": prompt_text}
    
    for attempt in range(3):
        try:
            print(f"[LOG] Calling Hugging Face model {model_id} (Attempt {attempt+1}/3)...", flush=True)
            res = requests.post(url, headers=headers, json=payload, timeout=60)
            
            if res.status_code == 200:
                return res.content
            elif res.status_code == 503:
                print("[WARN] Model is spinning up on Hugging Face servers. Waiting 20 seconds...", flush=True)
                time.sleep(20)
            else:
                print(f"[ERROR] Hugging Face API failed: {res.status_code} - {res.text[:100]}", flush=True)
                break
        except Exception as e:
            print(f"[ERROR] Network/Connection error on attempt {attempt+1}: {e}", flush=True)
            time.sleep(5)
            
    return None

def send_telegram_photo_bytes(bot_token, chat_id, image_bytes, caption):
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    
    with open("temp_cover.jpg", "wb") as f:
        f.write(image_bytes)
        
    with open("temp_cover.jpg", "rb") as photo:
        payload = {"chat_id": chat_id, "caption": caption[:1024], "parse_mode": "Markdown"}
        res = requests.post(url, data=payload, files={"photo": photo}, timeout=30)
        
        if res.status_code != 200:
            payload["parse_mode"] = ""
            photo.seek(0)
            res = requests.post(url, data=payload, files={"photo": photo}, timeout=30)
            
    print(f"[TELEGRAM PHOTO STATUS] HTTP {res.status_code}", flush=True)

def push_curated_to_telegram(title, body, image_prompts):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    hf_token = os.environ.get("HF_TOKEN")
    
    if not bot_token or not chat_id or not hf_token:
        raise ValueError("CRITICAL: Telegram or Hugging Face credentials missing!")

    models = [
        ("black-forest-labs/FLUX.1-schnell", "FLUX.1 (Hyper-Realism)"),
        ("stabilityai/stable-diffusion-xl-base-1.0", "SDXL (Cinematic)"),
        ("prompthero/openjourney", "OpenJourney (Stylized)")
    ]

    print("\n[LOG] Generating and dispatching 3 distinct Cover Image options...", flush=True)
    for idx, (prompt_text, model_info) in enumerate(zip(image_prompts, models), 1):
        model_id, label = model_info
        
        image_bytes = query_huggingface(model_id, prompt_text, hf_token)
        
        # IRON-CLAD BACKUP: If HF fails, reroute immediately to Pollinations high-end FLUX model
        if not image_bytes:
            print(f"[WARN] Hugging Face failed for {label}. Rerouting to Pollinations FLUX Engine...", flush=True)
            try:
                encoded = urllib.parse.quote(prompt_text)
                fallback_url = f"https://image.pollinations.ai/prompt/{encoded}?width=1200&height=800&nologo=true&model=flux"
                res = requests.get(fallback_url, timeout=30)
                if res.status_code == 200:
                    image_bytes = res.content
                    label = f"{label} [Fallback Engine]"
            except Exception as e:
                print(f"[ERROR] Fallback image engine also failed: {e}", flush=True)

        if image_bytes:
            caption = f"🎨 *COVER OPTION {idx} — {label}*\n\n*Prompt:* _{prompt_text}_"
            send_telegram_photo_bytes(bot_token, chat_id, image_bytes, caption)
        time.sleep(3)

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
