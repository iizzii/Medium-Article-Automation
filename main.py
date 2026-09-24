from news_fetcher import get_top_5_topics
from publisher import wait_for_user_selection, push_curated_to_telegram
from writer import generate_curated_draft
import sys

def main():
    print("\n" + "="*50, flush=True)
    print("[SYSTEM LOG] SINGLE VIRAL PIPELINE INITIATED", flush=True)
    print("="*50 + "\n", flush=True)

    print("[LOG] Fetching Top 5 Trending Topics from RSS...", flush=True)
    topics = get_top_5_topics()
    
    selected_topic = wait_for_user_selection(topics)
    print(f"\n[LOG] PROCEEDING WITH TOPIC: {selected_topic}\n", flush=True)
    
    print("[LOG] Handing off to Writer Engine...", flush=True)
    title, body, image_prompts = generate_curated_draft(selected_topic)

    print("\n[LOG] Handing off to Publisher Engine for Telegram Delivery...", flush=True)
    push_curated_to_telegram(title, body, image_prompts)
    
    print("\n" + "="*50, flush=True)
    print("[SYSTEM LOG] PIPELINE SUCCESSFULLY COMPLETED", flush=True)
    print("="*50 + "\n", flush=True)
    sys.exit(0)

if __name__ == "__main__":
    main()
