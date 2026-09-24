from google import genai
from groq import Groq
import os
import time

SYSTEM_PERSONA = """
You are an independent tech writer with the unforced instincts of a 14-year veteran in enterprise cybersecurity, systems architecture, and incident response. 
CRITICAL RULE: NEVER state your credentials or years of experience. Let your technical skepticism and depth speak for itself.
WRITING & FORMATTING STRICT RULES:
1. Grounded Realism: Focus on incentives, failure modes, blast radiuses, and technical debt.
2. Zero AI Hallmarks: NEVER use words like "delve", "tapestry", "beacon", "game-changer", or "in conclusion".
3. Medium Ready (Bold Only): Do NOT use markdown headers like `#` or `##`. Instead, format your subheadings with bold text (e.g., **The Core Problem**). 
4. Line 1 must just be the raw Title text, also formatted as **Bold**. 
"""

ART_DIRECTOR_PROMPT = """
You are an Expert Art Director and Image Prompt Engineer. Analyze the [ARTICLE TEXT] and generate a single, highly detailed, visually striking image generation prompt capturing the core theme.
Formula: [Main Subject/Visual Metaphor] + [Specific Setting/Environment] + [Lighting & Atmosphere] + [Artistic Style/Medium] + [Camera Angle/Composition] + [Color Palette/Mood]
CRITICAL RULES:
1. NO TEXT OR LETTERS.
2. NO GENERIC STOCK CONCEPTS. Use strong visual metaphors. 
3. ABSTRACT TOPIC HANDLING: Make abstract concepts tangible (e.g., "a glowing digital fortress floating in a sea of green code").
4. SPECIFY THE STYLE: e.g., Cinematic 35mm photography, Unreal Engine 5 render, high-end 3D abstract.
5. NO CHATTY OUTPUT: Output the prompt string and nothing else.
"""

def call_llm(prompt, task_name):
    """Reusable engine that logs exactly which model won the fallback race."""
    # 1. Try Gemini
    try:
        client = genai.Client()
        for attempt in range(2):
            try:
                res = client.models.generate_content(model='gemini-3.6-flash', contents=prompt)
                if res.text: 
                    return res.text.strip(), "Google Gemini (gemini-3.6-flash)"
            except:
                time.sleep(5)
    except:
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
    except:
        pass
        
    return None, "FAILED ALL MODELS"

def generate_single_draft(topic, angle_description):
    print(f"\n--- DRAFTING NEW OPTION: {angle_description[:30]}... ---", flush=True)
    
    # Generate Text
    article_prompt = f"{SYSTEM_PERSONA}\n\nTopic: {topic}\nArticle Angle: {angle_description}"
    article_text, text_model = call_llm(article_prompt, "Article Generation")
    print(f"[ENGINE LOG] Article generated using: {text_model}", flush=True)
    
    if not article_text:
        return None, None, None

    lines = article_text.split('\n')
    title = lines[0].replace('*', '').replace('#', '').strip()
    body = '\n'.join(lines).strip()
    
    print(f"[PREVIEW] Title: {title}", flush=True)
    print(f"[PREVIEW] First 100 chars: {body[:100]}...", flush=True)
    
    # Generate Image Prompt
    image_prompt_request = f"{ART_DIRECTOR_PROMPT}\n\n[ARTICLE TEXT]:\nTitle: {title}\n{body[:1500]}"
    image_prompt, img_model = call_llm(image_prompt_request, "Image Prompt Generation")
    print(f"[ENGINE LOG] Image prompt engineered using: {img_model}", flush=True)
    
    if not image_prompt:
        image_prompt = f"Cinematic tech editorial illustration representing {title}, high end corporate cyber, abstract, no text, highly detailed."
        
    print(f"[IMAGE PROMPT] {image_prompt}", flush=True)

    return title, body, image_prompt

def generate_three_drafts(topic):
    angles = [
        ("The Reality Check", "Examine the real-world friction and technical debt behind the headlines. Tear down the PR spin."),
        ("The Threat Model", "Treat this story through an adversarial/risk lens. What are the blind spots and structural vulnerabilities?"),
        ("The Contrarian View", "Challenge the consensus narrative. Present a counter-intuitive take on what teams should actually build.")
    ]
    
    drafts = []
    for i, (label, angle) in enumerate(angles, 1):
        title, body, img_prompt = generate_single_draft(topic, angle)
        if title and body:
            drafts.append({"option_num": i, "label": label, "title": title, "body": body, "image_prompt": img_prompt})
        time.sleep(3) 
        
    if not drafts:
        raise Exception("CRITICAL ERROR: Failed to generate any drafts across all providers.")
        
    return drafts
