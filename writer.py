from google import genai
from groq import Groq
import os
import time
import re

VIRAL_SYSTEM_PERSONA = """
You are an elite, viral tech essayist with the unspoken instincts of a 14-year veteran in enterprise cybersecurity and systems architecture.

VIRAL MEDIUM FORMULA (STRICT RULES):
1. The Hook: Open sentence 1 with a cold, uncomfortable observation or counter-intuitive truth. No greetings.
2. Length: Keep it tight and punchy: 400 to 550 words MAX (a 3-minute read). Zero filler.
3. Rhythm & White Space: Paragraphs must be 1 to 3 sentences maximum. Use single-sentence standalone lines for dramatic impact.
4. Voice: Skeptical, conversational, and direct. Expose the gap between PR/vendor theater and ground-level reality.
5. Banned AI Words: NEVER use "delve", "tapestry", "beacon", "game-changer", "testament", "crucial", "vital", or "in conclusion".

FORMATTING & BOLDING - CRITICAL:
- You MUST use HTML <b> tags for all bolding.
- Line 1 must be a highly catchy, tension-filled Title wrapped in <b> tags: <b>Catchy Title Here</b>
- Subheadings must be punchy, intriguing, and wrapped in <b> tags: <b>The Silent Threat</b>
- Skimmability: You MUST wrap 1 or 2 important keywords or punchlines in EVERY paragraph in <b> tags to make the best points pop out.

TAGS:
At the very end of your response, on a new line, write exactly the phrase "===TAGS===" followed by 5 highly relevant Medium hashtags separated by spaces.
"""

def generate_article(topic):
    print(f"\n[LOG] Drafting article for: {topic[:50]}...", flush=True)
    prompt = f"{VIRAL_SYSTEM_PERSONA}\n\nTopic: {topic}\nSpecific Angle: Give me the uncomfortable operational truth hidden behind this headline. Make it viral."
    
    article_text = None
    model_used = None

    # 1. PRIMARY: Try Gemini up to 5 times
    print("[LOG] Attempting Gemini API...", flush=True)
    client = genai.Client()
    for attempt in range(5):
        try:
            res = client.models.generate_content(model='gemini-3.6-flash', contents=prompt)
            if res.text:
                article_text = res.text.strip()
                model_used = "Google Gemini"
                break
        except Exception as e:
            print(f"[WARN] Gemini attempt {attempt+1}/5 failed: {e}. Retrying...", flush=True)
            time.sleep(10)

    # 2. FALLBACK: Groq Dynamic Search
    if not article_text:
        print("[WARN] Gemini failed 5 times. Falling back to Groq...", flush=True)
        groq_key = os.environ.get("GROQ_API_KEY")
        if groq_key:
            groq_client = Groq(api_key=groq_key)
            try:
                available = groq_client.models.list().data
                text_models = [m.id for m in available if "whisper" not in m.id.lower() and "guard" not in m.id.lower()]
                
                priority = [m for m in text_models if any(x in m.lower() for x in ["llama", "qwen", "mixtral", "gemma"])]
                models_to_try = priority + [m for m in text_models if m not in priority]
                
                for model_id in models_to_try:
                    try:
                        print(f"[LOG] Testing Groq model: {model_id}...", flush=True)
                        res = groq_client.chat.completions.create(
                            messages=[{"role": "user", "content": prompt}],
                            model=model_id,
                        )
                        article_text = res.choices[0].message.content.strip()
                        model_used = f"Groq ({model_id})"
                        break
                    except Exception:
                        continue
            except Exception as e:
                print(f"[ERROR] Groq routing failed: {e}", flush=True)

    if not article_text:
        raise Exception("CRITICAL ERROR: Failed to generate article across all providers.")

    print(f"[SUCCESS] Article generated using: {model_used}", flush=True)
    
    # Split the tags from the main body
    parts = article_text.split("===TAGS===")
    raw_body = parts[0].strip()
    tags = parts[1].strip() if len(parts) > 1 else "#TechNews #CyberSecurity #Innovation #SoftwareEngineering #TechTrends"
    
    # Extract Title and strip its tags for Telegram delivery separation
    lines = raw_body.split('\n')
    title = lines[0].replace('<b>', '').replace('</b>', '').replace('#', '').replace('*', '').strip()
    
    # Keep the rest of the body with its <b> tags intact
    body = '\n'.join(lines[1:]).strip()
    
    return title, body, tags
