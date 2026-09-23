from scraper import get_daily_topic
from writer import generate_draft
from publisher import push_to_medium

def main():
    topic, link = get_daily_topic()
    title, body = generate_draft(topic)
    push_to_medium(title, body)
    print("Workflow complete. Check your Medium Drafts folder.")

if __name__ == "__main__":
    main()
