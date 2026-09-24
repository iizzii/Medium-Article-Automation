from google import genai
from groq import Groq
import os
import time

def generate_draft(topic):
    print("Generating article...", flush=True)
    
    prompt = f"""
    You are a top Medium writer focusing on Indian corporate life and AI trends. 
    Write an engaging, 800-word article based on this trending topic: {topic}.
    
    Rules:
    1. The very first line must be the Title (No markdown formatting, just text).
    2. Write the rest of the article using Markdown (## headings, bullet points).
    3. Focus on the reality of Indian IT, startups, and AI impact. Tone should be relatable and insightful.
    4. Add a brief disclosure at the very end stating AI assisted in drafting.
    """
    
    response_text = None
    
    # ATTEMPT 1: Google Gemini
    print("Attempting generation with Google Gemini (gemini-3.6-flash)...", flush=True)
    try:
        client = genai.Client()
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model='gemini-3.6-flash',
                    contents=prompt
                )
                response_text = response.text
                print("Successfully generated draft using Google Gemini!", flush=True)
                break
            except Exception as e:
                if "503" in str(e) or "429" in str(e):
                    print(f"[Gemini] Busy or Quota hit. Retrying... (Attempt {attempt + 1} of 3)", flush=True)
                    time.sleep(15)
                else:
                    raise e
    except Exception as e:
        print(f"Gemini failed completely: {e}", flush=True)
        
    # ATTEMPT 2: Fallback to Groq (Llama 3)
    if not response_text:
        print("\nGoogle failed. Falling back to Groq (Meta Llama 3)...", flush=True)
        try:
            groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
            chat_completion = groq_client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                model="llama3-8b-8192", 
            )
            response_text = chat_completion.choices[0].message.content
            print("Successfully generated draft using Groq!", flush=True)
        except Exception as e:
            print(f"Groq failed: {e}", flush=True)
            
    if not response_text:
        raise Exception("CRITICAL: Both Gemini and Groq failed to generate content.")
        
    lines = response_text.strip().split('\n')
    title = lines[0].replace('#', '').replace('*', '').strip()
    body = '\n'.join(lines[1:]).strip()
    
    return title, body
