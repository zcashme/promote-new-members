import os
import sys
import json
import requests
from dotenv import load_dotenv
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

load_dotenv()

TRELLO_KEY = os.getenv("TRELLO_KEY")
TRELLO_TOKEN = os.getenv("TRELLO_TOKEN")
TRELLO_LIST_ID = os.getenv("TRELLO_LIST_ID")

MEMBER_ID = "6374510bf2aa0e0071120277"
LABEL_ID = "6924d2b9e964c12aa4cb9c9a"

if not all([TRELLO_KEY, TRELLO_TOKEN, TRELLO_LIST_ID]):
    raise Exception("Missing Trello environment variables.")


def create_trello_card(name: str, desc: str, due: str = None):
    url = "https://api.trello.com/1/cards"
    params = {
        "key": TRELLO_KEY,
        "token": TRELLO_TOKEN,
        "idList": TRELLO_LIST_ID,
        "name": name,
        "desc": desc,
        "pos": "top",
        "idMembers": MEMBER_ID,
        "idLabels": LABEL_ID
    }
    if due:
        params["due"] = due
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

    # Parse UTC timestamp from JSON
    # timestamp_utc is like "2025-12-09T10:48+00:00"
    dt_utc = datetime.fromisoformat(data['timestamp_utc'])
    
    # Convert to EST (America/New_York)
    # Note: We rely on ZoneInfo for correct offset (EST/EDT)
    est_idx = ZoneInfo("America/New_York")
    dt_est_end = dt_utc.astimezone(est_idx)
    dt_est_start = dt_est_end - timedelta(hours=24)

    # Format: 2025-12-10T09:00 am EST to 2025-12-11T09:00 am EST
    def format_est(dt):
        # Python strftime does not support %P for lowercase am/pm
        # We use %p (AM/PM) and replace it or use string manipulation
        s = dt.strftime("%Y-%m-%dT%I:%M %p EST")
        return s.replace("AM", "am").replace("PM", "pm")

    title = f"{format_est(dt_est_start)} to {format_est(dt_est_end)}"
    
    # Calculate Due Date: 1 PM EST = 18:00 UTC same day
    # We construct the ISO string for 18:00 UTC
    date_str = data['timestamp_utc'][:10]
    due_date = f"{date_str}T18:00:00Z"
    
    create_trello_card(title, desc, due_date)


if __name__ == "__main__":
    main()
