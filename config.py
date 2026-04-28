"""Shared config + constants for the FIGS tracker."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "tracker.db"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "300"))

# Seed list: (handle, preferred sizes). Handle = slug from the product URL.
# Sizes use the same format the dashboard shows: "M" for regular, "M Petite",
# "M Tall", etc. — pants need fit too.
SEED_PRODUCTS: list[tuple[str, list[str]]] = [
    ("womens-on-shift-contourknit-outerwear", ["M"]),
    ("womens-salta-under-scrubs", ["M"]),
    ("womens-ribbed-longsleeve-underscrub", ["M"]),
    ("womens-livingston-high-waisted-scrub-pants", ["M"]),
    ("womens-zamora-high-waisted-yoga-waistband-scrub-pants", ["M"]),
    ("womens-catarina-one-pocket-scrub-top", ["M"]),
]

FIGS_BASE = "https://www.wearfigs.com"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
