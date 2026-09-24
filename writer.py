from google import genai
from groq import Groq
import os
import time

SYSTEM_PERSONA = """
You are an independent tech writer with the unforced instincts of a 14-year veteran in enterprise cybersecurity, systems architecture, and incident response. 

CRITICAL RULE:
NEVER state your credentials or years of experience. Let your technical skepticism and depth speak for itself entirely through your analysis.

WRITING & FORMATTING STRICT RULES:
1. Grounded Realism: Focus on incentives, failure modes, blast radiuses, and technical debt.
2. Zero AI Hallmarks: NEVER use words like "delve", "tapestry", "beacon", "game-changer", or "in conclusion".
3. Medium Ready: Do NOT wrap the title in asterisks or markdown headers (e.g. no #). Line 1 must just be the raw Title text. 
4. The body must use standard Markdown (## for subheads, standard bullet points). Make it read naturally for Medium.
"""

def generate_single_draft(topic, angle_description):
    prompt = f"{SYSTEM_PERSONA}\n\nTopic: {topic}\nArticle Angle: {angle_description}"
    response_text = None
    
    try:
        client = genai.Client()
        for attempt in range(2):
            try:
                response = client.models.generate_content(model='gemini-3.6-flash', contents=prompt)
                response_text = response.text
                break
            except:
                time.sleep(8)
    except:
        pass
        
    if not response_text:
        try:
            groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
            available_models = groq_client.models.list().data
            text_models = [m.id for m in available_models if "whisper" not in m.id.lower() and "guard" not in m.id.lower()]
            
            if text_models:
                chat_completion = groq_client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model=text_models[0],
                )
                response_text = chat_completion.choices[0].message.content
        except:
            pass

    if not response_text: return None, None

    lines = response_text.strip().split('\n')
    title = lines[0].replace('#', '').replace('*', '').strip()
    body = '\n'.join(lines[1:]).strip()
    return title, body

def generate_three_drafts(topic):
    angles = [
        ("The Reality Check", "Examine the real-world friction and technical debt behind the headlines. Tear down the PR spin."),
        ("The Threat Model", "Treat this story through an adversarial/risk lens. What are the blind spots and structural vulnerabilities?"),
        ("The Contrarian View", "Challenge the consensus narrative. Present a counter-intuitive take on what teams should actually build.")
    ]
    
    drafts = []
    for i, (label, angle) in enumerate(angles, 1):
        title, body = generate_single_draft(topic, angle)
        if title and body:
            drafts.append({"option_num": i, "label": label, "title": title, "body": body})
        time.sleep(3) 
        
    if not drafts:
        raise Exception("Failed to generate any drafts across all providers.")
        
    return drafts
