from news_fetcher import get_trending_topic
from writer import generate_three_drafts
from publisher import push_options_to_telegram

def main():
    print("Fetching trending topic...", flush=True)
    topic = get_trending_topic()
    print(f"Selected Topic: {topic}\n", flush=True)

    print("Generating 3 humanized draft options...", flush=True)
    drafts = generate_three_drafts(topic)

    print("Dispatching to Telegram...", flush=True)
    push_options_to_telegram(drafts)
    print("All 3 options successfully delivered!", flush=True)

if __name__ == "__main__":
    main()
