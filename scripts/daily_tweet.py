import os
import json
import argparse
from supabase import create_client, Client
from urllib.parse import urlparse
import re
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone


load_dotenv()


# ---------------------------------------------------------
# 1. Setup Supabase API Client
# ---------------------------------------------------------
def get_supabase() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_API_KEY")
    if not url or not key:
        raise Exception("Missing SUPABASE_URL or SUPABASE_API_KEY in environment variables")
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
# 3. Compute timestamp (24h window)
# ---------------------------------------------------------
def compute_since(timestamp_override: str | None):
    if timestamp_override:
        try:
            t = datetime.fromisoformat(timestamp_override.replace("Z", "+00:00"))
        except:
            raise ValueError("Invalid timestamp format for --timestamp")
    else:
        t = datetime.now(timezone.utc)

    since = (t - timedelta(hours=24)).isoformat()
    return since, t


# ---------------------------------------------------------
# 4. Fetch new users
# ---------------------------------------------------------
def fetch_new_users(supabase, since_ts):
    res = (
        supabase
        .from_("zcasher_enriched")
        .select("id,name,created_at")
        .gte("created_at", since_ts)
        .execute()
    )

    users = res.data or []
    enriched = []

    for u in users:
        lid = u["id"]

        links = (
            supabase
            .from_("zcasher_links")
            .select("url,label")
            .eq("zcasher_id", lid)
            .execute()
        )

        twitter_url = None
        for link in (links.data or []):
            label = link.get("label", "").lower()
            if "twitter" in label or "x" in label:
                twitter_url = link["url"]
                break

        handle = extract_twitter_handle(twitter_url)

        enriched.append({
            "id": lid,
            "name": u["name"],
            "handle": handle,
            "twitter_url": twitter_url
        })

    return enriched


# ---------------------------------------------------------
# 5. Fetch new verifications
# ---------------------------------------------------------
def fetch_new_verified(supabase, since_ts):
    res = (
        supabase
        .from_("zcasher_verifications")
        .select("zcasher_id,verified_at,method,link_id")
        .gte("verified_at", since_ts)
        .eq("verified", True)
        .execute()
    )

    ver = res.data or []
    enriched = []

    for v in ver:
        uid = v["zcasher_id"]

        user_res = (
            supabase
            .from_("zcasher_enriched")
            .select("name")
            .eq("id", uid)
            .single()
            .execute()
        )
        name = user_res.data["name"]

        twitter_handle = None

        if v["link_id"]:
            link_res = (
                supabase
                .from_("zcasher_links")
                .select("url,label")
                .eq("id", v["link_id"])
                .single()
                .execute()
            )
            url = link_res.data.get("url")
            twitter_handle = extract_twitter_handle(url)

        enriched.append({
            "id": uid,
            "name": name,
            "handle": twitter_handle,
            "method": v["method"]
        })

    return enriched


# ---------------------------------------------------------
# 6. Build tweet drafts (two separate)
# ---------------------------------------------------------
def build_new_users_tweet(items, timestamp):
    fmt = lambda u: f"@{u['handle']}" if u["handle"] else u["name"]

    mentions_list = [fmt(u) for u in items]
    mentions_text = ", ".join(mentions_list)
    ps_mentions = " ".join([f"@{u['handle']}" for u in items if u["handle"]])

    return f"""🚀 New to ZcashMe (last 24 hours since {timestamp.strftime("%H:%M")} UTC): {len(items)}

Welcome: {mentions_text}

CTA: Help us welcome the newcomers — reply to this tweet or visit their ZcashMe profiles to say hi!

P.S. {ps_mentions} — easiest way to Zcash someone is to Zcash Me in your bio ;)
"""


def build_new_verified_tweet(items, timestamp):
    fmt = lambda u: f"@{u['handle']}" if u["handle"] else u["name"]

    mentions_list = [fmt(v) for v in items]
    mentions_text = ", ".join(mentions_list)
    ps_mentions = " ".join([f"@{v['handle']}" for v in items if v["handle"]])

    return f"""🔐 New verifications today (last 24 hours since {timestamp.strftime("%H:%M")} UTC): {len(items)}

Verified: {mentions_text}

CTA: Show some love — reply to confirm, follow, or check their ZcashMe profile.

P.S. {ps_mentions} — easiest way to Zcash someone is to Zcash Me in your bio ;)
"""


# ---------------------------------------------------------
# 7. Write JSON + MD
# ---------------------------------------------------------
def write_outputs(outdir, filename_base, tweet_text, data, timestamp):
    os.makedirs(outdir, exist_ok=True)

    # JSON version
    with open(os.path.join(outdir, f"{filename_base}.json"), "w", encoding="utf-8") as f:
        json.dump({
            "timestamp_utc": timestamp.isoformat(),
            "count": len(data),
            "items": data,
            "tweet": tweet_text
        }, f, indent=2)

    # Markdown version
    with open(os.path.join(outdir, f"{filename_base}.md"), "w", encoding="utf-8") as f:
        f.write(tweet_text)


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--timestamp", help="Override timestamp in UTC (ISO format)", default=None)
    parser.add_argument("--outdir", help="Directory to write drafts", default="drafts")
    parser.add_argument("--commit", action="store_true", help="Write files instead of console preview")
    args = parser.parse_args()

    supabase = get_supabase()

    since_ts, now_ts = compute_since(args.timestamp)

    print("Fetching new users…")
    new_users = fetch_new_users(supabase, since_ts)

    print("Fetching new verifications…")
    new_verified = fetch_new_verified(supabase, since_ts)

    tweet_users = build_new_users_tweet(new_users, now_ts)
    tweet_verified = build_new_verified_tweet(new_verified, now_ts)

    if args.commit:
        write_outputs(args.outdir, "new_users", tweet_users, new_users, now_ts)
        write_outputs(args.outdir, "new_verified", tweet_verified, new_verified, now_ts)
        print(f"\nDrafts written to {args.outdir}/")
        return

    print("\n====== NEW USERS TWEET PREVIEW ======\n")
    print(tweet_users)

    print("\n====== NEW VERIFIED TWEET PREVIEW ======\n")
    print(tweet_verified)


if __name__ == "__main__":
    main()
