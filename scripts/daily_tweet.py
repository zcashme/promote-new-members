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
    res = (
        supabase
        .from_("zcasher_enriched")
        .select("id,name,created_at")
        .gte("created_at", since)
        .execute()
    )

    rows = res.data or []
    enriched = []

    for u in rows:
        links = (
            supabase
            .from_("zcasher_links")
            .select("url,label")
            .eq("zcasher_id", u["id"])
            .execute()
        )

        twitter_url = None
        for link in (links.data or []):
            if "twitter" in link["label"].lower() or "x" in link["label"].lower():
                twitter_url = link["url"]
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
    res = (
        supabase
        .from_("zcasher_verifications")
        .select("zcasher_id,verified_at,method,link_id")
        .gte("verified_at", since)
        .eq("verified", True)
        .execute()
    )

    rows = res.data or []
    enriched = []

    for v in rows:
        ures = (
            supabase
            .from_("zcasher_enriched")
            .select("name")
            .eq("id", v["zcasher_id"])
            .single()
            .execute()
        )
        name = ures.data["name"]

        twitter_handle = None
        method = v["method"]

        if v["link_id"]:
            lres = (
                supabase
                .from_("zcasher_links")
                .select("url,label")
                .eq("id", v["link_id"])
                .single()
                .execute()
            )
            twitter_handle = extract_twitter_handle(lres.data.get("url"))

        enriched.append({
            "id": v["zcasher_id"],
            "name": name,
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
def write_markdown(ts, users, verified, tweet_users, tweet_verified):
    md_path = "drafts/daily_combined.md"

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

    print("Generated drafts/daily_combined.md")


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

    os.makedirs("drafts", exist_ok=True)

    payload = {
        "timestamp_utc": ts,
        "users": users,
        "verified": verified,
        "tweet_users": tweet_users,
        "tweet_verified": tweet_verified
    }

    with open("drafts/daily_combined.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print("Generated drafts/daily_combined.json")

    write_markdown(ts, users, verified, tweet_users, tweet_verified)


if __name__ == "__main__":
    main()
