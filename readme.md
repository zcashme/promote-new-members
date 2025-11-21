# 📘 **ZcashMe Promote-Bot — README**

A lightweight automation system that detects new ZcashMe users and new verifications, generates tweet-ready drafts, produces Markdown + JSON summaries, and creates promotional Trello cards. Runs daily via GitHub Actions and can also be triggered manually via a GitHub Pages frontend.

---

# 🚀 Project Overview

The Promote-Bot collects community growth data from Supabase, prepares daily promotional content, and publishes draft posts into Trello. These drafts help the team highlight new members and newly-verified profiles on Twitter.

---

# ✨ Features

* Detects **new users** (last 24 hours)
* Detects **new verifications** (Twitter/address/etc.)
* Generates **two tweet drafts**
* Produces **daily_combined.json** and **daily_combined.md**
* Creates **Trello cards** with tweet previews
* Safe Twitter handle extraction (x.com / twitter.com only)
* Works automatically (cron) or manually (frontend trigger)
* GitHub Actions integration + commit to `/drafts`

---

# 🧩 Architecture Summary

```
Supabase  --->  daily_tweet.py  --->  drafts/*.json + *.md
                       |
                       v
              create_trello_card.py
                       |
                       v
                    Trello List

Frontend (GitHub Pages) -> GitHub Actions -> Run workflow manually
```

**Components:**

* **Supabase** – source of user, link, and verification data
* **daily_tweet.py** – fetch, compute, and generate outputs
* **create_trello_card.py** – push cards into Trello
* **GitHub Actions** – scheduled + manual workflow
* **GitHub Pages frontend** – button to trigger manual runs

---

# 🗂 Data Sources (Supabase)

### **1) zcasher_enriched**

Used for:

* `id`
* `name`
* `created_at`

Purpose: detect new users in past 24h.

---

### **2) zcasher_links**

Used for:

* `label`
* `url`

Purpose: extract correct Twitter handle per user.

---

### **3) zcasher_verifications**

Used for:

* `zcasher_id`
* `method`
* `verified_at`
* `link_id`

Purpose: detect newly verified users and determine verification type.

---

# 🧠 Script Breakdown

## **scripts/daily_tweet.py**

Generates all daily outputs:

* Fetches new users & verifications (past 24h)
* Extracts Twitter handles safely
* Builds 2 separate tweet drafts
* Creates JSON:

  * `timestamp_utc`
  * `users`
  * `verified`
  * `tweet_users`
  * `tweet_verified`
* Creates Markdown summary with:

  * Tweet preview sections
  * Lists of users + verification details

Outputs:

* `drafts/daily_combined.json`
* `drafts/daily_combined.md`

---

## **.github/scripts/create_trello_card.py**

Responsible for sending results to Trello:

* Reads JSON files
* Builds a Trello-friendly Markdown description
* Adds card to top of defined Trello list (`pos="top"`)
* Uses `TRELLO_KEY`, `TRELLO_TOKEN`, `TRELLO_LIST_ID`

---

# 📄 Output Files

## **1. daily_combined.json**

Structure:

```
{
  timestamp_utc,
  users: [ { id, name, handle } ],
  verified: [ { id, name, handle, method } ],
  tweet_users,
  tweet_verified
}
```

---

## **2. daily_combined.md**

Contains:

* Timestamp
* New user count
* Tweet preview (new users)
* List of new users
* Verified count
* Tweet preview (verified)
* Verification details

This file is ideal for human review or inclusion inside Trello cards.

---

# 🖥 Frontend (GitHub Pages)

Purpose:

* Provide a "Generate Daily Promo" button
* Optionally override the timestamp
* Trigger the GitHub workflow manually via PAT API call

Frontend actions:

1. Sends request to GitHub Actions workflow_dispatch
2. Workflow receives optional `timestamp_utc`
3. Output files updated
4. Trello card created

Uses a minimal PAT with `public_repo` only.

[zcash.me/promote-new-members](https://zcashme.github.io/promote-new-members/)

---

# 🤖 GitHub Actions Workflow

Workflow name: **Promote new members**

Triggers:

* **Daily** at 09:00 UTC
* **Manual** (workflow_dispatch)

Performs:

1. Install Python dependencies
2. Run `daily_tweet.py` to generate drafts
3. Commit updated `/drafts`
4. Run `create_trello_card.py`
5. Create Trello card(s)

Repository permissions:

* `contents: write`
* `id-token: write`
* `actions: write` (for manual dispatch)

---

# 🔐 Required Secrets

| Secret Name      | Used For              |
| ---------------- | --------------------- |
| SUPABASE_URL     | Connect to Supabase   |
| SUPABASE_API_KEY | Auth for Supabase API |
| TRELLO_KEY       | Create Trello cards   |
| TRELLO_TOKEN     | Trello OAuth token    |
| TRELLO_LIST_ID   | Where cards are added |

Ensure all are added under:
**GitHub → Repo → Settings → Secrets → Actions**

---

# 🛠 Local Development

1. Clone repository
2. Activate the Virtual Environment:

   ```
   venv\Scripts\activate
   ```
3. Create `.env`:

   ```
   SUPABASE_URL=xxx
   SUPABASE_API_KEY=xxx
   TRELLO_KEY=xxx
   TRELLO_TOKEN=xxx
   TRELLO_LIST_ID=xxx
   ```
4. Run the daily generator:

   ```
   python scripts/daily_tweet.py
   ```
5. Check `/drafts` folder for JSON + MD
6. Create Trello card manually:

   ```
   python .github/scripts/create_trello_card.py drafts/daily_combined.json
   ```

---

# 🛠 Troubleshooting

### **1. Missing secrets**

Error:

```
Missing one of: SUPABASE_URL, SUPABASE_API_KEY...
```

Fix: Add missing secrets.

---

### **2. Trello “401 invalid key”**

Cause: Key/token mismatch
Fix: Regenerate API key + token from Trello Profile → API Key page.

---

### **3. Supabase “invalid URL”**

Cause: Wrong `SUPABASE_URL`
Fix: Copy URL exactly from Supabase Dashboard → Project Settings → API.

---

### **4. Drafts not committed**

Cause: Nothing changed
Fix: Normal behavior — no new users or verifications.

---

### **5. GitHub Pages frontend shows 404**

Cause: Pages not enabled
Fix:
GitHub → Settings → Pages → Source → `main` → `/docs`

---

