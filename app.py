"""Streamlit dashboard. Run with:  streamlit run app.py"""
import streamlit as st
import pandas as pd
from db import (
    init_db, get_dashboard_rows, set_tracking, get_user_sizes, set_user_sizes,
    alerts_enabled, set_alerts_enabled, conn,
)
from figs_client import fetch_product, parse_product
from config import FIGS_BASE

st.set_page_config(page_title="FIGS Tracker", page_icon="🩺", layout="wide")
init_db()

st.title("🩺 FIGS Price & Stock Tracker")
st.caption("Add a product, pick your size, get a Telegram ping when it goes on sale or restocks.")

# ---------- global controls ----------
top_l, top_r = st.columns([1, 3])
with top_l:
    on = st.toggle("Alerts ON", value=alerts_enabled())
    set_alerts_enabled(on)
with top_r:
    new_handle = st.text_input(
        "Add a FIGS product (paste the slug from the URL, e.g. `womens-salta-underscrub-tee`)",
        "",
    )
    if st.button("Add product") and new_handle.strip():
        raw = fetch_product(new_handle.strip())
        if raw:
            p = parse_product(raw)
            with conn() as c:
                c.execute(
                    "INSERT OR IGNORE INTO products(handle,title,image_url,tracking) VALUES(?,?,?,1)",
                    (p["handle"], p["title"], p["image_url"]),
                )
            st.success(f"Added {p['title']}")
            st.rerun()
        else:
            st.error("Couldn't fetch that product. Check the slug.")

st.divider()

# ---------- per-product cards ----------
rows = get_dashboard_rows()
if not rows:
    st.info("No products yet. Add one above, then start `python tracker.py` in another terminal.")
    st.stop()

df = pd.DataFrame(rows)

for handle, group in df.groupby("handle"):
    title = group["title"].iloc[0] or handle
    image_url = group["image_url"].iloc[0]
    tracking = bool(group["tracking"].iloc[0])

    with st.container(border=True):
        c1, c2 = st.columns([1, 4])
        with c1:
            if image_url:
                st.image(image_url, use_container_width=True)
        with c2:
            head_l, head_r = st.columns([4, 1])
            with head_l:
                st.subheader(title)
                st.caption(f"[{FIGS_BASE}/products/{handle}]({FIGS_BASE}/products/{handle})")
            with head_r:
                new_track = st.toggle("Tracking", value=tracking, key=f"track_{handle}")
                if new_track != tracking:
                    set_tracking(handle, new_track)
                    st.rerun()

            variants = group.dropna(subset=["variant_id"])
            if variants.empty:
                st.warning("No variant data yet. The tracker hasn't polled this product.")
                continue

            all_sizes = variants["size"].dropna().unique().tolist()
            current = get_user_sizes(handle)
            picked = st.multiselect(
                "Sizes to watch (empty = all)",
                options=all_sizes,
                default=[s for s in all_sizes if s in current],
                key=f"sizes_{handle}",
            )
            if set(picked) != current:
                set_user_sizes(handle, picked)

            view = variants.copy()
            view["sale?"] = view.apply(
                lambda r: "🔥" if r["compare_at_price"] and r["compare_at_price"] > r["price"] else "",
                axis=1,
            )
            view["stock"] = view["available"].apply(lambda a: "✅" if a else "❌")
            view = view[["size", "price", "compare_at_price", "sale?", "stock"]].rename(
                columns={"compare_at_price": "was"}
            )
            st.dataframe(view, hide_index=True, use_container_width=True)

st.divider()
with st.expander("Recent price changes"):
    with conn() as c:
        hist = c.execute(
            """SELECT p.title, v.size, h.price, h.compare_at_price, h.available, h.seen_at
               FROM price_history h
               JOIN variants v ON v.variant_id = h.variant_id
               JOIN products p ON p.handle = v.product_handle
               ORDER BY h.seen_at DESC LIMIT 50"""
        ).fetchall()
    if hist:
        st.dataframe(pd.DataFrame([dict(r) for r in hist]), hide_index=True, use_container_width=True)
    else:
        st.caption("No history yet.")
