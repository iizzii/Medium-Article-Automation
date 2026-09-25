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

def call_groq_safely(groq_client, prompt, task_name):
    """Dynamically fetches all available Groq models, prioritizes flagship ones, and tests until one works."""
    try:
        available = groq_client.models.list().data
        text_models = [m.id for m in available if "whisper" not in m.id.lower() and "guard" not in m.id.lower()]
        
        # Prioritize flagship AI families over experimental 3rd-party models
        priority = []
        others = []
        for m in text_models:
            m_lower = m.lower()
            if "llama" in m_lower or "qwen" in m_lower or "mixtral" in m_lower or "gemma" in m_lower:
                priority.append(m)
            else:
                others.append(m)
                
        models_to_try = priority + others
        
        for model_id in models_to_try:
            try:
                print(f"[LOG] Calling Groq API ({model_id}) for {task_name}...", flush=True)
                res = groq_client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model=model_id,
                )
                return res.choices[0].message.content.strip(), f"Groq ({model_id})"
            except Exception as e:
                # Catch 400s/404s cleanly and move instantly to the next model
                err_msg = str(e).split('\n')[0]
                print(f"[WARN] Groq model '{model_id}' bypassed: {err_msg}", flush=True)
                continue
    except Exception as e:
        print(f"[ERROR] Groq routing failed entirely: {e}", flush=True)
        
    return None, None

def call_gemini_safely(prompt, task_name):
    """Calls Gemini with extreme patience for high-traffic 503 spikes."""
    print(f"[WARN] Falling back to Gemini for {task_name}...", flush=True)
    client = genai.Client()
    max_retries = 10
    
    for attempt in range(max_retries):
        try:
            res = client.models.generate_content(model='gemini-3.6-flash', contents=prompt)
            if res.text:
                return res.text.strip(), "Google Gemini (gemini-3.6-flash)"
        except Exception as e:
            err_msg = str(e).split('\n')[0]
            if "503" in str(e) or "429" in str(e) or "500" in str(e):
                print(f"[WARN] Gemini server busy (Attempt {attempt+1}/{max_retries}). Retrying in 20s...", flush=True)
                time.sleep(20)
            else:
                print(f"[ERROR] Gemini {task_name} failed: {err_msg}", flush=True)
                break
                
    return None, None

def generate_curated_draft(topic):
    print(f"\n--- DRAFTING SINGLE VIRAL ARTICLE ---", flush=True)
    groq_api_key = os.environ.get("GROQ_API_KEY")
    groq_client = Groq(api_key=groq_api_key) if groq_api_key else None
    
    article_prompt = f"{VIRAL_SYSTEM_PERSONA}\n\nTopic: {topic}\nSpecific Angle: Give me the uncomfortable operational truth and structural threat model hidden behind this headline."
    
    article_text, text_model_used = None, None
    
    # 1. Try Groq Dynamic Search
    if groq_client:
        article_text, text_model_used = call_groq_safely(groq_client, article_prompt, "Article")
        
    # 2. Try Gemini Deep-Retry
    if not article_text:
        article_text, text_model_used = call_gemini_safely(article_prompt, "Article")
        
    if not article_text:
        raise Exception("CRITICAL ERROR: Failed to generate article across all providers.")

    print(f"[ENGINE LOG] Article generated using: {text_model_used}", flush=True)
    
    lines = article_text.split('\n')
    title = lines[0].replace('#', '').strip()
    body = '\n'.join(lines[1:]).strip()
    
    # Let rate limit buckets reset
    print("\n[LOG] Pausing for 15 seconds to respect AI API rate limits...", flush=True)
    time.sleep(15)
    
    image_prompt_request = f"{ART_DIRECTOR_PROMPT}\n\n[ARTICLE TEXT]:\nTitle: {title}\n{body[:1200]}"
    image_prompts_text, img_model_used = None, None
    
    # 3. Try Groq Dynamic Search for Prompts
    if groq_client:
        image_prompts_text, img_model_used = call_groq_safely(groq_client, image_prompt_request, "Image Prompts")
        
    # 4. Try Gemini Deep-Retry for Prompts
    if not image_prompts_text:
        image_prompts_text, img_model_used = call_gemini_safely(image_prompt_request, "Image Prompts")
            
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
