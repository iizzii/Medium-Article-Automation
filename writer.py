from google import genai
from groq import Groq
import os
import time

# Master Prompt engineered to embody a 14-year veteran practitioner without mentioning credentials
SYSTEM_PERSONA = """
You are an independent tech writer with the unforced instincts of someone who has spent 14 years in the trenches of enterprise cybersecurity, systems architecture, and incident response. 

CRITICAL IDENTITY RULE:
NEVER state your credentials, job title, or years of experience (e.g., never say "In my 14 years...", "As a security professional...", or "Throughout my career..."). 
Let your competence, technical skepticism, and depth speak for itself entirely through the way you analyze the problem.

WRITING PRINCIPLES:
1. Grounded Realism: You see through corporate spin, PR releases, and vendor marketing. You care about incentives, failure modes, threat models, blast radiuses, and technical debt.
2. Human Cadence: Vary your sentence lengths. Write with sharp, punchy observations. Use grounded analogies (e.g., prod outages at 2 AM, alert fatigue, audit theater) rather than textbook jargon.
3. Strict Negative Constraints: 
   - NEVER use AI cliches: "In today's fast-paced digital world", "delve", "testament", "beacon", "tapestry", "double-edged sword", "game-changer", "crucial", "vital", or "in conclusion".
   - Never start with a generic summary. Open directly with an uncomfortable observation or operational reality.
4. Medium Formatting:
   - Line 1 must be ONLY the Title (punchy, intriguing, no markdown symbols).
   - The rest must use clean Markdown (## headings, occasional bullet points, bold key insights).
   - Aim for ~700-800 words.
"""

def generate_single_draft(topic, angle_description):
    prompt = f"""
    {SYSTEM_PERSONA}

    Topic: {topic}
    Article Angle to Take: {angle_description}
    """
    
    response_text = None
    
    # ATTEMPT 1: Google Gemini (gemini-3.6-flash)
    try:
        client = genai.Client()
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model='gemini-3.6-flash',
                    contents=prompt
                )
                response_text = response.text
                break
            except Exception as e:
                if "503" in str(e) or "429" in str(e):
                    time.sleep(8)
                else:
                    break
    except Exception:
        pass
        
    # ATTEMPT 2: Fallback to Groq (llama-3.1-8b-instant)
    if not response_text:
        try:
            groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
            chat_completion = groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile",
            )
            response_text = chat_completion.choices[0].message.content
        except Exception as e:
            print(f"Groq generation error: {e}", flush=True)

    if not response_text:
        return None, None

    lines = response_text.strip().split('\n')
    title = lines[0].replace('#', '').replace('*', '').strip()
    body = '\n'.join(lines[1:]).strip()
    return title, body

def generate_three_drafts(topic):
    """Generates 3 distinct articles offering different strategic perspectives."""
    angles = [
        (
            "The Reality Check & Operational Breakdown",
            "Examine the real-world friction and technical debt behind the headlines. Tear down the executive PR spin and analyze what is actually breaking under the hood."
        ),
        (
            "The Threat Model & Unseen Risks",
            "Treat this story through an adversarial/risk lens. What are the second-order consequences, blind spots, and structural vulnerabilities being ignored?"
        ),
        (
            "The Contrarian Architecture View",
            "Challenge the consensus narrative. Present an experienced practitioner's counter-intuitive take on where real leverage lies and what teams should actually build or watch."
        )
    ]
    
    drafts = []
    for i, (label, angle) in enumerate(angles, 1):
        print(f"Drafting Option {i}: {label}...", flush=True)
        title, body = generate_single_draft(topic, angle)
        if title and body:
            drafts.append({
                "option_num": i,
                "label": label,
                "title": title,
                "body": body
            })
        time.sleep(3) # Safe breathing room between requests to protect rate limits
        
    if not drafts:
        raise Exception("Failed to generate any drafts across all providers.")
        
    return drafts
