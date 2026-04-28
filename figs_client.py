"""Pulls product data from FIGS.

The Shopify /products/<handle>.json endpoint is blocked, so we scrape the
JSON-LD <script type="application/ld+json"> block embedded in the HTML page.
That block exposes name, images, and one Offer per (color, fit, size) variant.
"""
import html as html_lib
import json
import re
from urllib.parse import parse_qs, urlparse

import requests

from config import FIGS_BASE, USER_AGENT

JSON_LD_RE = re.compile(
    r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
    re.S,
)


def _extract_jsonld_products(page_html: str) -> list[dict]:
    out = []
    for m in JSON_LD_RE.finditer(page_html):
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if isinstance(item, dict) and item.get("@type") == "Product":
                out.append(item)
    return out


def fetch_product(handle: str) -> dict | None:
    """Fetch and return the JSON-LD Product dict for a FIGS handle."""
    url = f"{FIGS_BASE}/products/{handle}"
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
        r.raise_for_status()
    except requests.RequestException:
        return None
    r.encoding = "utf-8"  # FIGS serves UTF-8 but doesn't always send the header
    products = _extract_jsonld_products(r.text)
    return products[0] if products else None


def _variant_id_from_offer(offer: dict) -> int:
    """JSON-LD has no numeric variant id, so derive a stable one from sku+color+size."""
    sku = offer.get("sku") or offer.get("url", "")
    return abs(hash(sku)) % (10 ** 12)


def _size_from_offer(offer: dict) -> str:
    """Extract a human-friendly size from the offer URL. Includes fit if non-regular."""
    url = html_lib.unescape(offer.get("url", ""))
    qs = parse_qs(urlparse(url).query)
    size = (qs.get("size") or [""])[0]
    fit = (qs.get("fit") or [""])[0]
    if fit and fit.lower() != "regular":
        return f"{size} {fit.title()}"
    return size or offer.get("sku", "?")


def _price_from_offer(offer: dict) -> tuple[float, float | None]:
    """Returns (price, compare_at_price). Picks the lowest price if multiple specs."""
    spec = offer.get("priceSpecification") or []
    if isinstance(spec, dict):
        spec = [spec]
    prices = [float(s["price"]) for s in spec if "price" in s]
    if not prices:
        # Fallback to top-level price field
        p = offer.get("price")
        return (float(p) if p is not None else 0.0, None)
    price = min(prices)
    compare_at = max(prices) if max(prices) > price else None
    return price, compare_at


def parse_product(product: dict) -> dict:
    """Normalize JSON-LD into the shape db.py expects."""
    images = product.get("image") or []
    if isinstance(images, str):
        images = [images]
    image_url = images[0] if images else ""

    offers = product.get("offers") or []
    if isinstance(offers, dict):
        offers = [offers]

    # Determine handle from @id (e.g. .../products/<handle>?color=...)
    pid = product.get("@id", "")
    path = urlparse(pid).path
    handle = path.rsplit("/", 1)[-1] if path else ""

    variants = []
    for offer in offers:
        price, compare_at = _price_from_offer(offer)
        availability = (offer.get("availability") or "").lower()
        available = "instock" in availability  # InStock / OutOfStock / etc.
        variants.append({
            "variant_id": _variant_id_from_offer(offer),
            "size": _size_from_offer(offer),
            "price": price,
            "compare_at_price": compare_at,
            "available": available,
        })

    return {
        "handle": handle,
        "title": product.get("name", handle),
        "image_url": image_url,
        "variants": variants,
    }
