from google import genai
import os
import time

def generate_draft(topic):
    print("Generating article with Gemini...", flush=True)
    
    client = genai.Client()
    
    prompt = f"""
    You are a top Medium writer focusing on Indian corporate life and AI trends. 
    Write an engaging, 800-word article based on this trending topic: {topic}.
    
    Rules:
    1. The very first line must be the Title (No markdown formatting, just text).
    2. Write the rest of the article using Markdown (## headings, bullet points).
    3. Focus on the reality of Indian IT, startups, and AI impact. Tone should be relatable and insightful.
    4. Add a brief disclosure at the very end stating AI assisted in drafting.
    """
    
    # List of models to try in order of preference
    fallback_models = ['gemini-3.6-flash', 'gemini-3.6-pro']
    
    response = None
    
    # Loop through each model in the list
    for current_model in fallback_models:
        print(f"\nAttempting generation with model: {current_model}...", flush=True)
        
        # Try each model 3 times before giving up and moving to the next backup
        max_retries = 3 
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model=current_model,
                    contents=prompt
                )
                break 
            except Exception as e:
                if "503" in str(e) or "429" in str(e) or "500" in str(e):
                    print(f"[{current_model}] Server busy. Retrying in 20 seconds... (Attempt {attempt + 1} of {max_retries})", flush=True)
                    time.sleep(20)
                else:
                    print(f"[{current_model}] Error: {e}", flush=True)
                    break 
        
        # If response was successfully generated, break the fallback loop early
        if response:
            print(f"Successfully generated draft using {current_model}!", flush=True)
            break 
            
    if not response:
        raise Exception("CRITICAL: All fallback models failed to generate content.")
        
    lines = response.text.strip().split('\n')
    title = lines[0].replace('#', '').replace('*', '').strip()
    body = '\n'.join(lines[1:]).strip()
    
    return title, body
