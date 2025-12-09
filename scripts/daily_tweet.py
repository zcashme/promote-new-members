import os
from supabase import create_client, Client
from urllib.parse import urlparse
import re
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
import json

load_dotenv()

# ---------------------------------------------------------
# 1. Setup Supabase API Client
# ---------------------------------------------------------
def get_supabase() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_API_KEY")
    return create_client(url, key)


# ---------------------------------------------------------
# 2. Safe Twitter handle extractor
# ---------------------------------------------------------
def extract_twitter_handle(url: str):
    if not url:
        return None

    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        if not (domain.endswith("x.com") or domain.endswith("twitter.com")):
            return None

        path = parsed.path.lstrip("/")
        if not path:
            return None

        candidate = path.split("/")[0]

        if candidate.lower() == "i":
            return None

        if re.match(r"^[A-Za-z0-9_]{1,15}$", candidate):
            return candidate

        return None
    except:
        return None


# ---------------------------------------------------------
# 3. Fetch new users (24h)
# ---------------------------------------------------------
def fetch_new_users(supabase, since):
    # Query the new view: zcasher_with_referral_rank
    # We also fetch the related links via the foreign key relationship if it exists.
    # Assuming "zcasher_links" is related to "zcasher_with_referral_rank" via "zcasher_id" -> "id"
    res = (
        supabase
        .from_("zcasher_with_referral_rank")
        .select("id,name,created_at, zcasher_links(label, url)")
        .gte("created_at", since)
        .execute()
    )

    rows = res.data or []
    enriched = []

    for u in rows:
        # The links are now nested in the response
        links = u.get("zcasher_links", [])
        
        twitter_url = None
        for link in links:
            label = link.get("label", "").lower()
            if "twitter" in label or "x" in label or "x.com" in label:
                twitter_url = link.get("url")
                break

        enriched.append({
            "id": u["id"],
            "name": u["name"],
            "handle": extract_twitter_handle(twitter_url)
        })

    return enriched


# ---------------------------------------------------------
# 4. Fetch newly verified (24h)
# ---------------------------------------------------------
def fetch_new_verified(supabase, since):
    # Query the new view for verified users
    # We filter by last_verified_at >= since
    res = (
        supabase
        .from_("zcasher_with_referral_rank")
        .select("id,name,last_verified_at, zcasher_links(label, url)")
        .gte("last_verified_at", since)
        .execute()
    )

    rows = res.data or []
    enriched = []

    for v in rows:
        # The links are now nested in the response
        links = v.get("zcasher_links", [])
        
        twitter_handle = None
        for link in links:
            label = link.get("label", "").lower()
            if "twitter" in label or "x" in label or "x.com" in label:
                twitter_handle = extract_twitter_handle(link.get("url"))
                if twitter_handle:
                    break

        # 'method' is not available in the new view, so we omit it or set a default.
        # The original code used it in the display. We'll set it to "Verified" or similar generic term.
        method = "Verified"

        enriched.append({
            "id": v["id"],
            "name": v["name"],
            "handle": twitter_handle,
            "method": method
        })

    return enriched


# ---------------------------------------------------------
# 5. Build tweets (two separate CTAs)
# ---------------------------------------------------------
def build_user_tweet(users, timestamp):
    tags = ", ".join("@" + u["handle"] for u in users if u["handle"])
    if not tags:
        tags = ", ".join(u["name"] for u in users)

    return (
        f"🚀 New to ZcashMe (last 24h since {timestamp} UTC): {len(users)}\n"
        f"Help us welcome: {tags}\n\n"
        f"P.S. Easiest way to Zcash you is ZcashMe in your bio 😉"
    )


def build_verified_tweet(vlist, timestamp):
    tags = ", ".join("@" + v["handle"] for v in vlist if v["handle"])
    if not tags:
        tags = ", ".join(v["name"] for v in vlist)

    return (
        f"🔐 Newly verified on ZcashMe (last 24h since {timestamp} UTC): {len(vlist)}\n"
        f"Props to: {tags}\n\n"
        f"P.S. Secure your ZcashMe profile to unlock full trust ✓"
    )


# ---------------------------------------------------------
# 6. Write Markdown report
# ---------------------------------------------------------
def write_markdown(ts, users, verified, tweet_users, tweet_verified, md_path):
    users_view = "\n".join(
        f"- {u['name']} ({'@'+u['handle'] if u['handle'] else 'no handle'})"
        for u in users
    )

    verified_view = "\n".join(
        f"- {v['name']} ({'@'+v['handle'] if v['handle'] else 'no handle'}) — {v['method']}"
        for v in verified
    )

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"""**Generated at:** {ts} UTC

---

# 🚀 New to ZcashMe (last 24h)
**Count:** {len(users)}

### 📝 Tweet Preview
{tweet_users}

### 👥 New Users
{users_view}

---

# 🔐 Newly Verified (last 24h)
**Count:** {len(verified)}

### 📝 Tweet Preview
{tweet_verified}

### 🔎 Verification Details
{verified_view}

---

This summary was automatically generated by the **ZcashMe Promote-Bot**.
""")

    print(f"Generated {md_path}")


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------
def main():
    supabase = get_supabase()

    now = datetime.now(timezone.utc)
    since = (now - timedelta(hours=24)).isoformat()
    ts = now.isoformat(timespec='minutes')

    users = fetch_new_users(supabase, since)
    verified = fetch_new_verified(supabase, since)

    tweet_users = build_user_tweet(users, ts)
    tweet_verified = build_verified_tweet(verified, ts)

    # Determine project root (parent of 'scripts')
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    drafts_dir = os.path.join(project_root, "drafts")
    
    os.makedirs(drafts_dir, exist_ok=True)

    json_path = os.path.join(drafts_dir, "daily_combined.json")
    md_path = os.path.join(drafts_dir, "daily_combined.md")

    payload = {
        "timestamp_utc": ts,
        "users": users,
        "verified": verified,
        "tweet_users": tweet_users,
        "tweet_verified": tweet_verified
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(f"Generated {json_path}")

    write_markdown(ts, users, verified, tweet_users, tweet_verified, md_path)


if __name__ == "__main__":
    main()
