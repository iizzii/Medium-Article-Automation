from groq import Groq
from google import genai
import os
import time
import re

VIRAL_SYSTEM_PERSONA = """
You are an elite, viral tech essayist with the unspoken instincts of a 14-year veteran in enterprise cybersecurity and systems architecture.

CRITICAL IDENTITY RULE:
NEVER mention your years of experience, credentials, or job title. Your authority comes entirely from your technical skepticism and surgical precision.

VIRAL MEDIUM FORMULA (STRICT RULES):
1. Length: Keep it tight and punchy: 400 to 550 words MAX (a 3-minute read). Zero filler.
2. The Hook: Open sentence 1 with a cold, uncomfortable observation or counter-intuitive truth. No greetings, no background setups.
3. Rhythm & White Space: 
   - Paragraphs must be 1 to 3 sentences maximum.
   - Use occasional single-sentence standalone lines for dramatic impact.
4. Highlight Bait: Include 2 to 3 standalone, razor-sharp maxims that practically force readers to highlight them on Medium.
5. Voice: Skeptical, conversational, and direct. Expose the gap between executive PR/vendor theater and ground-level technical reality.
6. Banned AI Words: NEVER use "delve", "tapestry", "beacon", "game-changer", "testament", "crucial", "vital", or "in conclusion".

FORMATTING - READ CAREFULLY:
- Do NOT use markdown headers like `#` or `##` anywhere in the text.
- To create a subheading, simply write the text and wrap it in double asterisks like this: **The Silent Threat**
- Line 1 must be the Title, wrapped in double asterisks: **Title Goes Here**
"""

ART_DIRECTOR_PROMPT = """
You are an Expert Art Director and Image Prompt Engineer. Analyze the [ARTICLE TEXT] and generate exactly THREE distinct, highly detailed, visually striking image generation prompts capturing the core theme.

The 3 visual styles must be entirely different from each other:
1. Cinematic realism/photographic (e.g., highly detailed, moody, dramatic lighting)
2. High-end 3D abstract/metaphorical render (e.g., Unreal Engine 5, glowing data, architectural)
3. Minimalist graphic editorial (e.g., high-contrast, stylized, retro-futuristic)

CRITICAL RULES:
1. NO TEXT OR LETTERS IN ANY IMAGE.
2. NO GENERIC STOCK CONCEPTS (no businessmen shaking hands, no generic laptops). Use tangible visual metaphors.
3. Format your output strictly as a numbered list with the raw prompts ONLY.
"""

def generate_curated_draft(topic):
    print(f"\n--- DRAFTING SINGLE VIRAL ARTICLE ---", flush=True)
    groq_api_key = os.environ.get("GROQ_API_KEY")
    groq_client = Groq(api_key=groq_api_key)
    
    article_prompt = f"{VIRAL_SYSTEM_PERSONA}\n\nTopic: {topic}\nSpecific Angle: Give me the uncomfortable operational truth and structural threat model hidden behind this headline."
    
    article_text = None
    text_model_used = None
    
    # 1. Try Groq for Article Generation
    try:
        available_models = groq_client.models.list().data
        text_models = [m.id for m in available_models if "whisper" not in m.id.lower() and "guard" not in m.id.lower()]
        if text_models:
            text_model_used = text_models[0]
            print(f"[LOG] Calling Groq API ({text_model_used}) for Article...", flush=True)
            res = groq_client.chat.completions.create(
                messages=[{"role": "user", "content": article_prompt}],
                model=text_model_used,
            )
            article_text = res.choices[0].message.content.strip()
    except Exception as e:
        print(f"[ERROR] Groq text generation failed: {e}", flush=True)
        
    # 2. Fallback to Gemini if Groq fails
    if not article_text:
        print("[WARN] Falling back to Gemini for article generation...", flush=True)
        try:
            client = genai.Client()
            res = client.models.generate_content(model='gemini-3.6-flash', contents=article_prompt)
            article_text = res.text.strip()
            text_model_used = "Google Gemini (gemini-3.6-flash)"
        except Exception as e:
            raise Exception(f"CRITICAL ERROR: Failed to generate article across all providers. {e}")

    print(f"[ENGINE LOG] Article generated using: {text_model_used}", flush=True)
    
    lines = article_text.split('\n')
    title = lines[0].replace('#', '').strip()
    body = '\n'.join(lines[1:]).strip()
    
    # Let the API rate limits cool down
    print("\n[LOG] Pausing for 15 seconds to respect AI API rate limits...", flush=True)
    time.sleep(15)
    
    image_prompt_request = f"{ART_DIRECTOR_PROMPT}\n\n[ARTICLE TEXT]:\nTitle: {title}\n{body[:1200]}"
    image_prompts_text = None
    img_model_used = None
    
    # 3. Try Groq for Image Prompts
    try:
        if text_model_used and "Groq" in text_model_used:
            print(f"[LOG] Calling Groq API ({text_model_used}) for Image Prompts...", flush=True)
            res = groq_client.chat.completions.create(
                messages=[{"role": "user", "content": image_prompt_request}],
                model=text_model_used,
            )
            image_prompts_text = res.choices[0].message.content.strip()
            img_model_used = f"Groq ({text_model_used})"
    except Exception as e:
        print(f"[ERROR] Groq failed for image prompts: {e}", flush=True)
        
    # 4. Fallback to Gemini for Image Prompts
    if not image_prompts_text:
        try:
            client = genai.Client()
            res = client.models.generate_content(model='gemini-3.6-flash', contents=image_prompt_request)
            image_prompts_text = res.text.strip()
            img_model_used = "Google Gemini (gemini-3.6-flash)"
        except Exception as e:
            print(f"[ERROR] Gemini failed for image prompts: {e}", flush=True)
            
    print(f"[ENGINE LOG] Image prompts engineered using: {img_model_used}", flush=True)
    
    image_prompts = []
    if image_prompts_text:
        matches = re.findall(r'^\d+\.\s*(.+)', image_prompts_text, flags=re.MULTILINE)
        if matches:
            image_prompts = [m.strip() for m in matches[:3]]
    
    # Failsafe if regex misses
    while len(image_prompts) < 3:
        image_prompts.append(f"Cinematic tech editorial illustration representing {title}, high end corporate cyber, abstract, no text, highly detailed.")

    return title, body, image_prompts
