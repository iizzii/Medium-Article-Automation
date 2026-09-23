import feedparser
import random

def get_daily_topic():
    print("Fetching trending news...")
    rss_url = "https://news.google.com/rss/search?q=AI+jobs+layoffs+corporate+culture+India&hl=en-IN&gl=IN&ceid=IN:en"
    feed = feedparser.parse(rss_url)
    
    top_entries = feed.entries[:5]
    selected_story = random.choice(top_entries)
    
    print(f"Selected Topic: {selected_story.title}")
    return selected_story.title, selected_story.link
