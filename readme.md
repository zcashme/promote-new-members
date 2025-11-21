# 📝 **Daily Twitter Bot – Documentation**

## **Overview**

This bot generates **daily automated tweets** for the ZcashMe project.
It identifies:

1. **New users** who joined ZcashMe in the last 24 hours
2. **New verifications** completed in the last 24 hours
3. Handles **Twitter/X URL extraction safely** to tag users only when valid

The bot currently:

* Fetches data using **Supabase API** (Anon key, safe read-only)
* Builds a daily tweet
* Prints it to console for testing (no posting yet)
* Handled via `daily_tweet.py`

Future step: integrate with Twitter API + GitHub Actions automation.

---

# 📁 **Project Structure**

```
Twitter-bot/
│
├── scripts/
│   └── daily_tweet.py        # Main bot script
│
├── .env                      # Supabase API environment variables
│
└── README.md (this file)
```

---

# 🔑 **Environment Variables (.env)**

Create a file named `.env` in project root:

```
SUPABASE_URL=https://<yourproject>.supabase.co
SUPABASE_API_KEY=your_supabase_anon_key
```

These values are available at:
**Supabase → Project Settings → API**

Use the **Anon Key** unless explicitly permitted to use service_role.

---

# ⚙️ **How the Bot Works (Workflow)**

## 1. Load Environment

`python-dotenv` loads `.env` so secrets are available to Python.

## 2. Connect to Supabase

Using:

```python
create_client(SUPABASE_URL, SUPABASE_API_KEY)
```

This creates a REST-based client (NOT direct Postgres).
The bot does **not** access the DB directly → safe for contributors.

---

## 3. Determine “last 24 hours”

In Python:

```python
since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
```

This creates a timestamp like:

```
2025-01-03T19:05:22.421Z
```

This timestamp is used for filtering rows in both queries.

---

## 4. Fetch New Users (last 24 hours)

The bot queries Supabase:

```python
supabase.from_("zcasher_enriched")
        .select("id,name,created_at")
        .gte("created_at", since)
```

Then for each user, it fetches their links from `zcasher_links`:

```python
supabase.from_("zcasher_links")
        .select("url,label")
        .eq("zcasher_id", user_id)
```

Finally, it extracts a **Twitter handle** (if valid).

This results in something like:

```python
{
  "id": 150,
  "name": "AliceZ",
  "handle": "alice_crypto"
}
```

---

## 5. Fetch Newly Verified Users

Query:

```python
supabase.from_("zcasher_verifications")
        .select("zcasher_id,verified_at,method,link_id")
        .gte("verified_at", since)
        .eq("verified", True)
```

Then:

* Fetch user name
* Fetch the link tied to the verification
* Extract Twitter handle from that URL

---

# 🧠 **Twitter Handle Extraction Logic**

This logic is crucial because ZcashMe users may add links like:

* `https://x.com/username`
* `https://x.com/username/status/123`
* `https://x.com/i/web/status/...` (no actual username)
* `https://github.com/foo`
* `https://forum.zcashcommunity.com/u/bar`
* Random websites

The bot **must tag only valid Twitter handles**, never wrong ones.

## Python logic:

```python
parsed = urlparse(url)
domain = parsed.netloc.lower()

# Only accept x.com or twitter.com
if not (domain.endswith("x.com") or domain.endswith("twitter.com")):
    return None

path = parsed.path.lstrip("/")
candidate = path.split("/")[0]

if candidate.lower() == "i":
    return None

if re.match(r"^[A-Za-z0-9_]{1,15}$", candidate):
    return candidate
```

## Rules enforced:

✔ Valid domain: `x.com` or `twitter.com`
✔ Only the first path segment is used
✔ Skip `/i/web/status/...`
✔ Valid username regex: `^[A-Za-z0-9_]{1,15}$`
✔ No tagging for GitHub, forum links, Telegram, etc
✔ Prevents accidental tagging of unrelated users

---

# 💬 **Tweet Format**

Final generated tweet:

```
🚀 New to ZcashMe (last 24h): <count>
Welcome: <handle_or_name_list>

🔐 New verifications today: <count>
Verified: <handle_or_name_list>

Keep it private. Keep it zcashy. ⚡️
#Zcash #ZcashMe #Privacy
```

This matches the desired **community + hype + crypto tone**.

---

# 🧪 **SQL Equivalent Queries**

These match Python logic exactly and can be run inside Supabase SQL Editor to verify the results.

---

## 🔍 SQL 1: New Users in last 24h

```sql
WITH twitter_links AS (
    SELECT
        zcasher_id,
        url,
        label,
        CASE
            WHEN regexp_replace(lower(url), '^https?://(www\.)?', '') ~ '^(x\.com|twitter\.com)/' THEN
                CASE
                    WHEN split_part(regexp_replace(url, '^https?://(www\.)?(x\.com|twitter\.com)/', '', 'i'), '/', 1) ~ '^[A-Za-z0-9_]{1,15}$'
                         AND split_part(regexp_replace(url, '^https?://(www\.)?(x\.com|twitter\.com)/', '', 'i'), '/', 1) <> 'i'
                    THEN split_part(regexp_replace(url, '^https?://(www\.)?(x\.com|twitter\.com)/', '', 'i'), '/', 1)
                    ELSE NULL
                END
            ELSE NULL
        END AS twitter_handle
    FROM zcasher_links
    WHERE lower(label) LIKE '%twitter%' OR lower(label) LIKE '%x%'
)

SELECT
    u.id AS zcasher_id,
    u.name,
    u.created_at,
    tl.url AS twitter_url,
    tl.twitter_handle
FROM zcasher_enriched u
LEFT JOIN twitter_links tl
       ON tl.zcasher_id = u.id
WHERE u.created_at >= (now() - interval '24 hours')
ORDER BY u.created_at DESC;
```

---

## 🔍 SQL 2: Newly Verified in last 24h

```sql
WITH twitter_links AS (
    SELECT
        id AS link_id,
        zcasher_id,
        url,
        label,
        CASE
            WHEN regexp_replace(lower(url), '^https?://(www\.)?', '') ~ '^(x\.com|twitter\.com)/' THEN
                CASE
                    WHEN split_part(regexp_replace(url, '^https?://(www\.)?(x\.com|twitter\.com)/', '', 'i'), '/', 1) ~ '^[A-Za-z0-9_]{1,15}$'
                         AND split_part(regexp_replace(url, '^https?://(www\.)?(x\.com|twitter\.com)/', '', 'i'), '/', 1) <> 'i'
                    THEN split_part(regexp_replace(url, '^https?://(www\.)?(x\.com|twitter\.com)/', '', 'i'), '/', 1)
                    ELSE NULL
                END
            ELSE NULL
        END AS twitter_handle
    FROM zcasher_links
)

SELECT
    v.zcasher_id,
    e.name,
    v.verified_at,
    v.method,
    tl.url AS twitter_url,
    tl.twitter_handle
FROM zcasher_verifications v
LEFT JOIN zcasher_enriched e
    ON v.zcasher_id = e.id
LEFT JOIN twitter_links tl
    ON tl.link_id = v.link_id
WHERE v.verified = true
  AND v.verified_at >= (now() - interval '24 hours')
ORDER BY v.verified_at DESC;
```

---

# 🧪 **Testing Locally**

### 1. Install dependencies

```
pip install supabase python-dotenv
```

### 2. Create `.env` file

Add SUPABASE_URL and SUPABASE_API_KEY

### 3. Run the script

```
python scripts/daily_tweet.py
```

You should see:

```
Fetching new users…
Fetching newly verified…
====== DAILY TWEET PREVIEW ======
...
```

### 4. Compare with SQL Output

Run the SQL above in Supabase → SQL Editor
Ensure results match Python.

---

# 🔄 **Next Steps (optional)**

* Add more rules to extract the exact twitter profile
* Add **GitHub Actions** scheduler to run daily
* Add **Twitter API integration** to post automatically
* Add weekly / monthly scripts
* Add logging table to avoid duplicate posts
* Add RPC functions in Supabase to reduce client-side logic