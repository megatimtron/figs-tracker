"""Public read-only FIGS dashboard for Streamlit Community Cloud.

Fetches live from FIGS on every load (cached 5 min). No DB, no writes.
Tracking + alerts happen separately via GitHub Actions in the same repo.
"""
import streamlit as st
import pandas as pd

from config import SEED_PRODUCTS, FIGS_BASE
from figs_client import fetch_product, parse_product

st.set_page_config(page_title="FIGS Tracker", page_icon="🩺", layout="wide")

st.title("🩺 FIGS Tracker")
st.caption(
    "Live prices and stock for the products being watched. "
    "Telegram alerts run automatically every 15 min via GitHub Actions."
)


@st.cache_data(ttl=300, show_spinner=False)
def load_product(handle: str) -> dict | None:
    raw = fetch_product(handle)
    return parse_product(raw) if raw else None


with st.spinner("Fetching live FIGS data..."):
    products = []
    for handle, watched_sizes in SEED_PRODUCTS:
        p = load_product(handle)
        if p:
            products.append((p, set(watched_sizes)))

if not products:
    st.error("Couldn't fetch any products. FIGS may be blocking the request — try refreshing.")
    st.stop()

# ---------- top-line summary ----------
on_sale_now = []
for p, sizes in products:
    for v in p["variants"]:
        if sizes and v["size"] not in sizes:
            continue
        if v["compare_at_price"] and v["compare_at_price"] > v["price"]:
            on_sale_now.append((p["title"], v))

if on_sale_now:
    st.success(f"🔥 {len(on_sale_now)} watched item(s) currently on sale!")
    for title, v in on_sale_now:
        pct = (1 - v["price"] / v["compare_at_price"]) * 100
        st.write(
            f"**{title}** ({v['size']}) — "
            f"${v['price']:.2f} (was ${v['compare_at_price']:.2f}, **{pct:.0f}% off**)"
        )
else:
    st.info("No watched items on sale right now. You'll get a Telegram ping when one drops.")

st.divider()

# ---------- per-product cards ----------
for p, watched_sizes in products:
    with st.container(border=True):
        c1, c2 = st.columns([1, 4])
        with c1:
            if p["image_url"]:
                st.image(p["image_url"], use_container_width=True)
        with c2:
            st.subheader(p["title"])
            url = f"{FIGS_BASE}/products/{p['handle']}"
            watched_str = ", ".join(sorted(watched_sizes)) if watched_sizes else "all sizes"
            st.caption(f"[{url}]({url}) — watching: **{watched_str}**")

            view = pd.DataFrame(p["variants"])
            view["watched"] = view["size"].apply(
                lambda s: "👁️" if (not watched_sizes or s in watched_sizes) else ""
            )
            view["sale"] = view.apply(
                lambda r: "🔥" if r["compare_at_price"] and r["compare_at_price"] > r["price"] else "",
                axis=1,
            )
            view["stock"] = view["available"].apply(lambda a: "✅" if a else "❌")
            view = view[["watched", "size", "price", "compare_at_price", "sale", "stock"]].rename(
                columns={"compare_at_price": "was"}
            )
            st.dataframe(view, hide_index=True, use_container_width=True)

st.divider()
st.caption(
    "Settings (which products and sizes to watch) live in `config.py` in the GitHub repo. "
    "Data refreshes every 5 min."
)
