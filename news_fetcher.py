import feedparser

def get_top_5_topics():
    rss_url = "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=en-IN&gl=IN&ceid=IN:en"
    feed = feedparser.parse(rss_url)
    
    if not feed.entries:
        return [
            "The hidden technical debt of AI integration",
            "Why Zero Trust is failing in Indian startups",
            "The truth behind enterprise cloud security",
            "Alert fatigue in modern SOCs",
            "Balancing speed and security in 2026"
        ]
        
    return [entry.title for entry in feed.entries[:5]]
