from google import genai
import os
import time

def generate_draft(topic):
    print("Generating article with Gemini...")
    
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
    
    # Retry logic: Try up to 3 times if the server is busy
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model='gemini-3.6-flash',
                contents=prompt
            )
            break # If successful, exit the retry loop
        except Exception as e:
            if "503" in str(e) or "429" in str(e):
                print(f"Server busy. Retrying in 30 seconds... (Attempt {attempt + 1} of {max_retries})")
                time.sleep(30)
                if attempt == max_retries - 1:
                    raise Exception("Failed after maximum retries.") from e
            else:
                raise e # If it's a different error, crash normally
    
    lines = response.text.strip().split('\n')
    title = lines[0].replace('#', '').replace('*', '').strip()
    body = '\n'.join(lines[1:]).strip()
    
    return title, body
