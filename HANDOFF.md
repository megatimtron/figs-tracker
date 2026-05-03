# Handoff Notes — FIGS Tracker

Status snapshot for picking this project back up on a different machine / Claude Code instance. Last updated 2026-05-02.

## What this is

A FIGS.com price + restock tracker. Polls FIGS every 15 min via GitHub Actions, pings Telegram when watched sizes go on sale or restock. A local Streamlit dashboard manages the watchlist; a public read-only Streamlit dashboard shows live prices.

Repo: **github.com/megatimtron/figs-tracker**

## Architecture

```
figs_client.py   ← scrapes JSON-LD from FIGS product HTML (Shopify /products/X.json is blocked)
       ↓
tracker.py       ← polling loop. `--once` mode for the GitHub Actions cron.
       ↓
db.py            ← SQLite (tracker.db). Source of truth shared by tracker + dashboard + CI.
       ↓
telegram_notify  ← sendMessage wrapper. Reads TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID from env.

app.py           ← local Streamlit dashboard (read+write). Add products, pick sizes, toggle alerts.
streamlit_app.py ← public read-only dashboard for Streamlit Community Cloud. Live-fetches, no DB.
config.py        ← env loading + SEED_PRODUCTS list (6 items, all "M" by default).
.github/workflows/track.yml ← cron every 15 min, runs `tracker.py --once`, commits tracker.db.
```

### Data flow

1. GitHub Actions cron fires every 15 min → `python tracker.py --once`
2. For each product where `tracking=1`, fetch JSON-LD, diff against `variants` row.
3. On change, insert `price_history` row. If watched size + (sale newly triggered OR restock), send Telegram + log to `alert_log` (24h dedupe).
4. Workflow commits `tracker.db` back to the repo so state persists.

## Schema (SQLite)

- `products` — handle PK, title, image_url, tracking flag, last_checked
- `variants` — variant_id PK (derived from sku hash), product_handle FK, size, price, compare_at_price, available
- `price_history` — append-only log of every variant change
- `user_sizes` — (product_handle, size) — which sizes to alert on. Empty = all sizes.
- `settings` — k/v. Currently just `alerts_enabled`.
- `alert_log` — variant_id, kind ("sale" | "restock"), price, sent_at. Used for dedupe.

## Important quirks

1. **FIGS blocks the Shopify JSON endpoint.** We scrape the JSON-LD `<script type="application/ld+json">` block from the HTML. If FIGS changes their template, `figs_client.py` is the first place to look.
2. **Variant IDs are synthetic** — derived from `hash(sku) % 10^12` because JSON-LD doesn't expose Shopify's numeric variant ids.
3. **Sizes include fit when non-regular** — e.g. `"M"`, `"M Petite"`, `"M Tall"`. Pulled from the offer URL's query string (`?fit=...&size=...`).
4. **Two writers to one SQLite file.** GitHub Actions and local `app.py` both write `tracker.db`. README warns the user to push local changes before the next cron tick to avoid merge conflicts.
5. **Free GitHub Actions minutes** — ~290 min/mo on the current cadence. Repo should be **public** to get unlimited minutes (the db is just price snapshots, no PII).

## Setup on a new machine

```bash
git clone https://github.com/megatimtron/figs-tracker.git
cd figs-tracker
python -m venv .venv && source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env  # then fill in TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID
streamlit run app.py
```

`.env` is gitignored — get the values from BotFather / `getUpdates` per the README, or copy from the original machine.

## Loose ends / TODO

- [ ] **Deploy `streamlit_app.py` to Streamlit Community Cloud.** The file exists and works locally; just needs a `share.streamlit.io` deploy pointing at this repo, main file `streamlit_app.py`. No env vars needed — it's read-only and doesn't use Telegram.
- [ ] **Add a "test alert" button** to `app.py` so the user can verify Telegram works without waiting for a real sale.
- [ ] **Surface last-checked time** on the dashboard so it's clear the cron is alive.
- [ ] **Consider compacting `price_history`** — append-only, will grow forever. Probably fine for a year+ at current volume but worth noting.
- [ ] **No tests.** ~400 LOC of glue code; would be nice to have at least a parser test for `figs_client.parse_product` since that's the most fragile part.

## Original spec

Came from a "build a wife-friendly FIGS tracker" prompt. The original scope was:
- Streamlit dashboard with size filter and start/stop button ✅
- Telegram alerts on `compare_at_price` trigger ✅
- SQLite/JSON persistence ✅
- Sale alert message format ✅

Then expanded to cloud hosting (GitHub Actions) so it doesn't need a laptop running 24/7, plus restock alerts and price history.
