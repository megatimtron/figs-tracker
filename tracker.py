"""Poller. Two modes:
   python tracker.py          # loop forever, sleep POLL_INTERVAL_SECONDS between cycles
   python tracker.py --once   # one cycle then exit (used by GitHub Actions cron)

Sends a Telegram alert when a tracked size goes on sale or restocks.
"""
import sys
import time
from db import (
    init_db, upsert_product, upsert_variant, get_user_sizes,
    alerts_enabled, already_alerted, log_alert, conn,
)
from figs_client import fetch_product, parse_product
from telegram_notify import send
from config import SEED_PRODUCTS, POLL_INTERVAL_SECONDS, FIGS_BASE


def seed_products():
    """Make sure the seed handles exist as rows, with their preferred sizes."""
    with conn() as c:
        for handle, sizes in SEED_PRODUCTS:
            c.execute(
                "INSERT OR IGNORE INTO products(handle,title,image_url,tracking) VALUES(?,?,?,1)",
                (handle, handle, ""),
            )
            for s in sizes:
                c.execute(
                    "INSERT OR IGNORE INTO user_sizes(product_handle,size) VALUES(?,?)",
                    (handle, s),
                )


def get_tracked_handles() -> list[str]:
    with conn() as c:
        rows = c.execute("SELECT handle FROM products WHERE tracking=1").fetchall()
        return [r["handle"] for r in rows]


def check_one(handle: str):
    raw = fetch_product(handle)
    if not raw:
        print(f"[poll] {handle}: fetch failed")
        return
    p = parse_product(raw)
    upsert_product(p["handle"], p["title"], p["image_url"])

    user_sizes = get_user_sizes(p["handle"])
    send_alerts = alerts_enabled()

    for v in p["variants"]:
        prev, changed = upsert_variant(
            v["variant_id"], p["handle"], v["size"],
            v["price"], v["compare_at_price"], v["available"],
        )

        if not send_alerts or not changed or prev is None:
            continue
        # Only alert for sizes the user cares about (or all if none chosen).
        if user_sizes and v["size"] not in user_sizes:
            continue

        url = f"{FIGS_BASE}/products/{p['handle']}"

        # Sale trigger: compare_at_price newly set (and > price).
        on_sale_now = v["compare_at_price"] and v["compare_at_price"] > v["price"]
        was_on_sale = prev["compare_at_price"] and prev["compare_at_price"] > prev["price"]
        if on_sale_now and not was_on_sale and not already_alerted(v["variant_id"], "sale", v["price"]):
            msg = (
                f"🚨 <b>FIGS SALE ALERT!</b>\n"
                f"{p['title']} ({v['size']}) is now <b>${v['price']:.2f}</b> "
                f"(was ${v['compare_at_price']:.2f}).\n"
                f"Buy it before it sells out!\n{url}"
            )
            if send(msg):
                log_alert(v["variant_id"], "sale", v["price"])

        # Restock trigger: was unavailable, now available.
        if v["available"] and not prev["available"] and not already_alerted(v["variant_id"], "restock", v["price"]):
            msg = (
                f"📦 <b>Back in stock:</b> {p['title']} ({v['size']}) — "
                f"${v['price']:.2f}\n{url}"
            )
            if send(msg):
                log_alert(v["variant_id"], "restock", v["price"])


def run_cycle():
    for handle in get_tracked_handles():
        try:
            check_one(handle)
        except Exception as e:
            print(f"[tracker] {handle}: {e}")


def main():
    init_db()
    seed_products()
    if "--once" in sys.argv:
        print("[tracker] one-shot mode")
        run_cycle()
        return
    print(f"[tracker] polling every {POLL_INTERVAL_SECONDS}s. Ctrl+C to stop.")
    while True:
        run_cycle()
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
