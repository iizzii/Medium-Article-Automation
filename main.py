from news_fetcher import get_top_5_topics
from publisher import wait_for_user_selection, push_options_to_telegram
from writer import generate_three_drafts

def main():
    print("Fetching Top 5 Topics...", flush=True)
    topics = get_top_5_topics()
    
    # This will pause the GitHub Action until you reply on Telegram (max 10 mins)
    selected_topic = wait_for_user_selection(topics)
    
    print(f"Generating 3 drafts for: {selected_topic}", flush=True)
    drafts = generate_three_drafts(selected_topic)

    print("Dispatching finalized articles to Telegram...", flush=True)
    push_options_to_telegram(drafts)
    print("All done!", flush=True)

if __name__ == "__main__":
    main()
