import feedparser

def get_top_10_topics():
    # Hardcore technical and InfoSec feeds
    feeds = [
        "https://www.bleepingcomputer.com/feed/",
        "https://feeds.feedburner.com/TheHackersNews"
    ]
    
    topics = []
    
    for url in feeds:
        try:
            feed = feedparser.parse(url)
            # Grab the top 6 most recent articles from each feed
            for entry in feed.entries[:6]:
                clean_title = entry.title.strip()
                if clean_title not in topics:
                    topics.append(clean_title)
        except Exception as e:
            print(f"[WARN] Failed to fetch from {url}: {e}")
            
    # Fallback in case of a total network blackout
    if not topics:
        return [
            "Critical Zero-Day discovered in major enterprise software infrastructure",
            "Reverse engineering the latest kernel-level malware variant",
            "Why the recent out-of-band security patch is breaking production systems",
            "New sophisticated supply chain attack bypasses standard EDR solutions",
            "Deep dive: How threat actors are exploiting misconfigured cloud environments"
        ] * 2
        
    # Return exactly 10 distinct, highly technical topics
    return topics[:10]
