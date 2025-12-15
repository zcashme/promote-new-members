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


import argparse

def format_description(data):
    """
    Formats the description as requested:
    
    Warm welcomes to
    🆕Name (@handle)
    ...
    
    If it's really you, put your http://Zcash.me in your X bio!
    
    
    Now Verified:
    
    ✅Name (no handle)
    ...
    
    Zm your friends today!
    """
    lines = []
    # 1. Warm welcomes
    users = data.get('users', [])
    if users:
        lines.append("Warm welcomes to")
        for u in users:
            name = u.get('name', 'Unknown')
            handle = u.get('handle')
            if handle:
                lines.append(f"🆕{name} (@{handle})")
            else:
                lines.append(f"🆕{name}")
        
        # Add footer for new users
        lines.append("If it's really you, put your http://Zcash.me in your X bio!")
        lines.append("")
        lines.append("")
    
    # 2. Now Verified
    verified = data.get('verified', [])
    if verified:
        lines.append("Now Verified:")
        lines.append("")
        for v in verified:
            name = v.get('name', 'Unknown')
            handle = v.get('handle')
            if handle:
                lines.append(f"✅{name} (@{handle})")
            else:
                lines.append(f"✅{name} (no handle)")
                
        lines.append("")
        lines.append("Zm your friends today!")
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Create Trello card from daily digest JSON.")
    parser.add_argument("json_path", help="Path to drafts/daily_combined.json")
    parser.add_argument("--dry-run", action="store_true", help="Print description instead of creating card")
    
    args = parser.parse_args()
    json_path = args.json_path
    
    if not os.path.exists(json_path):
        print(f"Error: JSON file not found at {json_path}")
        return

    # Read JSON for data
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Generate new description format
    desc = format_description(data)
    
    if args.dry_run:
        print("=== Trello Card Description Preview ===")
        print(desc)
        print("=====================================")
        return

    # Parse UTC timestamp from JSON
    # timestamp_utc is like "2025-12-09T10:48+00:00"
    dt_utc = datetime.fromisoformat(data['timestamp_utc'])
    
    # Convert to EST (America/New_York)
    est_idx = ZoneInfo("America/New_York")
    dt_est_end = dt_utc.astimezone(est_idx)
    dt_est_start = dt_est_end - timedelta(hours=24)

    # Format: 2025-12-10T09:00 am EST to 2025-12-11T09:00 am EST
    def format_est(dt):
        s = dt.strftime("%Y-%m-%dT%I:%M %p EST")
        return s.replace("AM", "am").replace("PM", "pm")

    title = f"{format_est(dt_est_start)} to {format_est(dt_est_end)}"
    
    # Calculate Due Date: 1 PM EST = 18:00 UTC same day
    date_str = data['timestamp_utc'][:10]
    due_date = f"{date_str}T18:00:00Z"
    
    create_trello_card(title, desc, due_date)


if __name__ == "__main__":
    main()
