from google import genai
import os

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
    
    # Updated to the new 3.6 model
    response = client.models.generate_content(
        model='gemini-3.6-flash',
        contents=prompt
    )
    
    lines = response.text.strip().split('\n')
    title = lines[0].replace('#', '').replace('*', '').strip()
    body = '\n'.join(lines[1:]).strip()
    
    return title, body
