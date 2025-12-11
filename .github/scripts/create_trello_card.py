import os
import sys
import json
import requests
from dotenv import load_dotenv

load_dotenv()

TRELLO_KEY = os.getenv("TRELLO_KEY")
TRELLO_TOKEN = os.getenv("TRELLO_TOKEN")
TRELLO_LIST_ID = os.getenv("TRELLO_LIST_ID")

MEMBER_ID = "6374510bf2aa0e0071120277"

if not all([TRELLO_KEY, TRELLO_TOKEN, TRELLO_LIST_ID]):
    raise Exception("Missing Trello environment variables.")


def create_trello_card(name: str, desc: str):
    url = "https://api.trello.com/1/cards"
    params = {
        "key": TRELLO_KEY,
        "token": TRELLO_TOKEN,
        "idList": TRELLO_LIST_ID,
        "name": name,
        "desc": desc,
        "pos": "top",
        "idMembers": MEMBER_ID
    }
    r = requests.post(url, params=params)
    if r.status_code >= 300:
        print("Trello API error:", r.status_code, r.text)
        raise Exception("Failed to create Trello card")
    print("Created Trello card:", r.json().get("url"))


def main():
    if len(sys.argv) < 2:
        print("Usage: python create_trello_cards.py drafts/daily_combined.json")
        return

    json_path = sys.argv[1]
    
    # Infer markdown path from json path
    # e.g. drafts/daily_combined.json -> drafts/daily_combined.md
    md_path = json_path.replace(".json", ".md")

    if not os.path.exists(md_path):
        print(f"Error: Markdown file not found at {md_path}")
        return

    # Read JSON for the title timestamp
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Read Markdown for the card description
    with open(md_path, "r", encoding="utf-8") as f:
        desc = f.read()

    # Extract just the date (YYYY-MM-DD) from the timestamp
    # timestamp_utc is like "2025-12-09T10:48"
    date_str = data['timestamp_utc'][:10]
    title = date_str
    
    create_trello_card(title, desc)


if __name__ == "__main__":
    main()
