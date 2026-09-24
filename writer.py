from google import genai
from groq import Groq
import os
import time

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
   - Use **Bold Subheadings** to keep the piece intensely skimmable.
4. Highlight Bait: Include 2 to 3 standalone, razor-sharp maxims that practically force readers to highlight them on Medium.
5. Voice: Skeptical, conversational, and direct. Expose the gap between executive PR/vendor theater and ground-level technical reality.
6. Banned AI Words: NEVER use "delve", "tapestry", "beacon", "game-changer", "testament", "crucial", "vital", or "in conclusion".
7. Format:
   - Line 1: **Title** (Punchy, tension-filled, high curiosity—no cheap clickbait).
   - Body: Clean text using **bold headers** for sections and bold inline emphasis on critical punchlines.
"""

ART_DIRECTOR_PROMPT = """
You are an Expert Art Director and Image Prompt Engineer. Analyze the [ARTICLE TEXT] and generate a single, highly detailed, visually striking image generation prompt capturing the core theme.

Formula: [Main Subject/Visual Metaphor] + [Specific Setting/Environment] + [Lighting & Atmosphere] + [Artistic Style/Medium] + [Camera Angle/Composition] + [Color Palette/Mood]

CRITICAL RULES:
1. NO TEXT OR LETTERS IN THE IMAGE.
2. NO GENERIC STOCK CONCEPTS (no businessmen shaking hands, no generic laptops). Use tangible visual metaphors.
3. SPECIFY HIGH-END MEDIUM: e.g., Cinematic 35mm photography, Unreal Engine 5 render, or high-contrast architectural editorial.
4. NO CHATTY OUTPUT: Output the prompt string and nothing else.
"""

def call_llm(prompt, task_name):
    """Fallback engine: Tries Gemini first, then dynamically routes to an active Groq text model."""
    # 1. Try Gemini
    try:
        client = genai.Client()
        for _ in range(2):
            try:
                res = client.models.generate_content(model='gemini-3.6-flash', contents=prompt)
                if res.text: 
                    return res.text.strip(), "Google Gemini (gemini-3.6-flash)"
            except Exception:
                time.sleep(4)
    except Exception:
        pass
        
    # 2. Try Groq Dynamic
    try:
        groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        available_models = groq_client.models.list().data
        text_models = [m.id for m in available_models if "whisper" not in m.id.lower() and "guard" not in m.id.lower()]
        
        if text_models:
            model_to_use = text_models[0]
            res = groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=model_to_use,
            )
            if res.choices: 
                return res.choices[0].message.content.strip(), f"Groq ({model_to_use})"
    except Exception:
        pass
        
    return None, "FAILED ALL MODELS"

def generate_single_draft(topic, angle_description):
    print(f"\n--- DRAFTING VIRAL OPTION: {angle_description[:30]}... ---", flush=True)
    
    article_prompt = f"{VIRAL_SYSTEM_PERSONA}\n\nTopic: {topic}\nSpecific Angle: {angle_description}"
    article_text, text_model = call_llm(article_prompt, "Article Generation")
    print(f"[ENGINE LOG] Article generated using: {text_model}", flush=True)
    
    if not article_text:
        return None, None, None

    lines = article_text.split('\n')
    title = lines[0].replace('*', '').replace('#', '').strip()
    body = '\n'.join(lines[1:]).strip()
    
    print(f"[PREVIEW] Title: {title}", flush=True)
    print(f"[PREVIEW] Word Count: ~{len(body.split())} words", flush=True)
    
    # Generate bespoke Art Director prompt for the image
    image_prompt_request = f"{ART_DIRECTOR_PROMPT}\n\n[ARTICLE TEXT]:\nTitle: {title}\n{body[:1200]}"
    image_prompt, img_model = call_llm(image_prompt_request, "Image Prompt Generation")
    print(f"[ENGINE LOG] Image prompt engineered using: {img_model}", flush=True)
    
    if not image_prompt:
        image_prompt = f"Cinematic minimalist tech editorial illustration representing {title}, atmospheric lighting, abstract infrastructure, no text."

    return title, body, image_prompt

def generate_three_drafts(topic):
    angles = [
        ("The Uncomfortable Truth", "Expose the unspoken failure mode or corporate illusion behind the headline. Call out the vanity metrics and theater."),
        ("The Second-Order Threat", "Unpack the cascading technical and organizational risks that everyone is sleeping on. Frame it through incentives and blast radius."),
        ("The Contrarian Playbook", "Challenge conventional wisdom. Give practitioners a sharp, counter-intuitive rule of thumb on what actually works.")
    ]
    
    drafts = []
    for i, (label, angle) in enumerate(angles, 1):
        title, body, img_prompt = generate_single_draft(topic, angle)
        if title and body:
            drafts.append({
                "option_num": i,
                "label": label,
                "title": title,
                "body": body,
                "image_prompt": img_prompt
            })
        time.sleep(2) 
        
    if not drafts:
        raise Exception("CRITICAL ERROR: Failed to generate drafts across all providers.")
        
    return drafts
