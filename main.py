from news_fetcher import get_top_10_topics
from publisher import wait_for_user_selection, push_article_to_telegram
from writer import generate_article
import sys

def main():
    print("\n" + "="*50, flush=True)
    print("[SYSTEM LOG] TEXT-ONLY VIRAL PIPELINE INITIATED", flush=True)
    print("="*50 + "\n", flush=True)

    print("[LOG] Fetching Top 10 Trending Topics...", flush=True)
    topics = get_top_10_topics()
    
    selected_topic = wait_for_user_selection(topics)
    print(f"\n[LOG] PROCEEDING WITH TOPIC: {selected_topic}\n", flush=True)
    
    title, body = generate_article(selected_topic)

    push_article_to_telegram(title, body)
    
    print("\n" + "="*50, flush=True)
    print("[SYSTEM LOG] PIPELINE SUCCESSFULLY COMPLETED", flush=True)
    print("="*50 + "\n", flush=True)
    sys.exit(0)

if __name__ == "__main__":
    main()
