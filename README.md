# FIGS Tracker

Get a Telegram ping when items on FIGS.com go on sale or restock in your size. The tracker runs in the cloud on GitHub Actions (free), so nothing has to stay running on your laptop.

- **GitHub Actions** runs `tracker.py --once` every 15 min, sends alerts, commits the updated db back.
- **Streamlit dashboard** (`app.py`) is just for managing what to track and which sizes — run it locally whenever you want to tweak settings.

## One-time setup

### 1. Telegram bot (~2 min)

1. In Telegram, search **@BotFather**, send `/newbot`, follow prompts. It gives you a **bot token** — save it.
2. Search the bot you made, send it any message ("hi"). Required so it can DM you.
3. In a browser visit `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` and find `"chat":{"id":123456789,...}`. That number is your **chat id**.

### 2. Push this repo to GitHub

```bash
git init
git add .
git commit -m "initial"
gh repo create figs-tracker --private --source=. --push
```

### 3. Add the secrets

GitHub repo → Settings → Secrets and variables → Actions → New repository secret. Add two:

- `TELEGRAM_BOT_TOKEN` — the token from BotFather
- `TELEGRAM_CHAT_ID` — your chat id

### 4. Done

The workflow (`.github/workflows/track.yml`) runs every 15 min automatically. To test now: Actions tab → "FIGS tracker" → Run workflow.

## Local dashboard (optional, for changing settings)

```bash
pip install -r requirements.txt
streamlit run app.py
```

Add products by URL slug, pick sizes, toggle alerts. Then `git add tracker.db && git commit && git push` — next cron run picks up your changes.

> Heads up: the dashboard and the cloud both write to `tracker.db`. If you change settings locally, push before the next cron run or you'll get a merge conflict on the bot's commit.

## Notes

- Alerts dedupe within 24h per (variant, kind, price) so you won't get spammed.
- `price_history` keeps every change — useful for spotting fake "sales."
- GitHub cron is best-effort; runs can be 5-10 min late under load. Fine for shopping.
- Free GitHub Actions limit is 2000 min/mo for private repos. This uses ~3 min/run × 96 runs/day ≈ 290 min/mo. Make the repo **public** to get unlimited free minutes (the db is just price snapshots, nothing sensitive).
