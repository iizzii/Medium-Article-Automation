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
You are an Expert Art Director and Image Prompt Engineer. Your task is to analyze the provided [ARTICLE TEXT] and generate a single, highly detailed, visually striking image generation prompt that perfectly captures the core theme of the article.

Do not summarize the article. Do not write a description of the article. Output ONLY the raw image generation prompt to be fed directly into an AI image generator.

Use this strict formula to construct the prompt:
[Main Subject/Visual Metaphor] + [Specific Setting/Environment] + [Lighting & Atmosphere] + [Artistic Style/Medium] + [Camera Angle/Composition] + [Color Palette/Mood]

CRITICAL RULES FOR GENERATION:
1. NO TEXT OR LETTERS: AI image generators struggle with text. Never ask for signs, labels, or words in the image.
2. NO GENERIC STOCK CONCEPTS: Avoid boring literal interpretations. Use strong visual metaphors instead. 
3. ABSTRACT TOPIC HANDLING: If the article is abstract, generate a tangible visual metaphor (e.g., "a glowing digital fortress floating in a sea of green code").
4. SPECIFY THE STYLE: Always dictate a high-end visual medium (e.g., Cinematic 35mm photography, 3D isometric Unreal Engine render, etc).
5. NO CHATTY OUTPUT: Do not say "Here is your prompt." Output the prompt string and nothing else.
"""

def call_llm(prompt):
    """Reusable fallback engine: Tries Gemini, then dynamically finds a working Groq model."""
    try:
        client = genai.Client()
        for _ in range(2):
            try:
                res = client.models.generate_content(model='gemini-3.6-flash', contents=prompt)
                if res.text: return res.text.strip()
            except:
                time.sleep(5)
    except:
        pass
        
    try:
        groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        available_models = groq_client.models.list().data
        text_models = [m.id for m in available_models if "whisper" not in m.id.lower() and "guard" not in m.id.lower()]
        
        if text_models:
            res = groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=text_models[0],
            )
            if res.choices: return res.choices[0].message.content.strip()
    except:
        pass
        
    return None

def generate_single_draft(topic, angle_description):
    # 1. Generate the article
    article_prompt = f"{SYSTEM_PERSONA}\n\nTopic: {topic}\nArticle Angle: {angle_description}"
    article_text = call_llm(article_prompt)
    
    if not article_text:
        return None, None, None

    lines = article_text.split('\n')
    title = lines[0].replace('*', '').replace('#', '').strip()
    body = '\n'.join(lines).strip() # Keep title in the body for easy copy-paste
    
    # 2. Generate the bespoke image prompt
    image_prompt_request = f"{ART_DIRECTOR_PROMPT}\n\n[ARTICLE TEXT]:\nTitle: {title}\n{body[:1500]}"
    image_prompt = call_llm(image_prompt_request)
    
    if not image_prompt:
        image_prompt = f"Cinematic tech editorial illustration representing {title}, high end corporate cyber, abstract, no text, highly detailed."

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
        raise Exception("Failed to generate any drafts across all providers.")
        
    return drafts
