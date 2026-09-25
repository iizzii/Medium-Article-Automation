import feedparser

def get_top_10_topics():
    rss_url = "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=en-IN&gl=IN&ceid=IN:en"
    feed = feedparser.parse(rss_url)
    
    if not feed.entries:
        return ["The hidden technical debt of AI integration"] * 10
        
    return [entry.title for entry in feed.entries[:10]]
