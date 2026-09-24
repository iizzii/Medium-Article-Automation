import feedparser
import random

def get_trending_topic():
    # Fetches top tech news from Google News India
    rss_url = "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=en-IN&gl=IN&ceid=IN:en"
    feed = feedparser.parse(rss_url)
    
    if not feed.entries:
        return "The hidden technical debt of AI integration in enterprise cybersecurity"
        
    # Select one of the top 5 trending headlines to ensure variety every day
    top_entries = feed.entries[:5]
    selected = random.choice(top_entries)
    
    return selected.title
