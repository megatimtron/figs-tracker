"""SQLite layer. One file, shared by tracker.py (writer) and app.py (reader/writer)."""
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from config import DB_PATH


SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    handle TEXT PRIMARY KEY,
    title TEXT,
    image_url TEXT,
    tracking INTEGER DEFAULT 1,
    last_checked TEXT
);

CREATE TABLE IF NOT EXISTS variants (
    variant_id INTEGER PRIMARY KEY,
    product_handle TEXT,
    size TEXT,
    price REAL,
    compare_at_price REAL,
    available INTEGER,
    FOREIGN KEY (product_handle) REFERENCES products(handle)
);

CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    variant_id INTEGER,
    price REAL,
    compare_at_price REAL,
    available INTEGER,
    seen_at TEXT
);

CREATE TABLE IF NOT EXISTS user_sizes (
    product_handle TEXT,
    size TEXT,
    PRIMARY KEY (product_handle, size)
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS alert_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    variant_id INTEGER,
    kind TEXT,
    price REAL,
    sent_at TEXT
);
"""


@contextmanager
def conn():
    c = sqlite3.connect(DB_PATH, timeout=10)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init_db():
    with conn() as c:
        c.executescript(SCHEMA)
        cur = c.execute("SELECT value FROM settings WHERE key='alerts_enabled'")
        if cur.fetchone() is None:
            c.execute("INSERT INTO settings(key,value) VALUES('alerts_enabled','1')")


def now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


# ---------- products / variants ----------

def upsert_product(handle: str, title: str, image_url: str):
    with conn() as c:
        c.execute(
            """INSERT INTO products(handle,title,image_url,tracking,last_checked)
               VALUES(?,?,?,1,?)
               ON CONFLICT(handle) DO UPDATE SET
                 title=excluded.title,
                 image_url=excluded.image_url,
                 last_checked=excluded.last_checked""",
            (handle, title, image_url, now()),
        )


def upsert_variant(variant_id: int, handle: str, size: str,
                   price: float, compare_at: float | None, available: bool):
    with conn() as c:
        prev = c.execute(
            "SELECT price, compare_at_price, available FROM variants WHERE variant_id=?",
            (variant_id,),
        ).fetchone()

        c.execute(
            """INSERT INTO variants(variant_id,product_handle,size,price,compare_at_price,available)
               VALUES(?,?,?,?,?,?)
               ON CONFLICT(variant_id) DO UPDATE SET
                 size=excluded.size,
                 price=excluded.price,
                 compare_at_price=excluded.compare_at_price,
                 available=excluded.available""",
            (variant_id, handle, size, price, compare_at, int(available)),
        )

        changed = (
            prev is None
            or prev["price"] != price
            or prev["compare_at_price"] != compare_at
            or prev["available"] != int(available)
        )
        if changed:
            c.execute(
                """INSERT INTO price_history(variant_id,price,compare_at_price,available,seen_at)
                   VALUES(?,?,?,?,?)""",
                (variant_id, price, compare_at, int(available), now()),
            )
        return prev, changed


def get_dashboard_rows():
    with conn() as c:
        rows = c.execute(
            """SELECT p.handle, p.title, p.image_url, p.tracking,
                      v.variant_id, v.size, v.price, v.compare_at_price, v.available
               FROM products p
               LEFT JOIN variants v ON v.product_handle = p.handle
               ORDER BY p.title, v.size"""
        ).fetchall()
        return [dict(r) for r in rows]


def set_tracking(handle: str, on: bool):
    with conn() as c:
        c.execute("UPDATE products SET tracking=? WHERE handle=?", (int(on), handle))


# ---------- user prefs ----------

def get_user_sizes(handle: str) -> set[str]:
    with conn() as c:
        rows = c.execute(
            "SELECT size FROM user_sizes WHERE product_handle=?", (handle,)
        ).fetchall()
        return {r["size"] for r in rows}


def set_user_sizes(handle: str, sizes: list[str]):
    with conn() as c:
        c.execute("DELETE FROM user_sizes WHERE product_handle=?", (handle,))
        c.executemany(
            "INSERT INTO user_sizes(product_handle,size) VALUES(?,?)",
            [(handle, s) for s in sizes],
        )


def alerts_enabled() -> bool:
    with conn() as c:
        r = c.execute("SELECT value FROM settings WHERE key='alerts_enabled'").fetchone()
        return r and r["value"] == "1"


def set_alerts_enabled(on: bool):
    with conn() as c:
        c.execute(
            "INSERT INTO settings(key,value) VALUES('alerts_enabled',?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            ("1" if on else "0",),
        )


# ---------- alert dedupe ----------

def already_alerted(variant_id: int, kind: str, price: float) -> bool:
    """Avoid spamming: don't re-alert same kind+price for same variant within a day."""
    with conn() as c:
        r = c.execute(
            """SELECT 1 FROM alert_log
               WHERE variant_id=? AND kind=? AND price=?
                 AND sent_at > datetime('now','-1 day')""",
            (variant_id, kind, price),
        ).fetchone()
        return r is not None


def log_alert(variant_id: int, kind: str, price: float):
    with conn() as c:
        c.execute(
            "INSERT INTO alert_log(variant_id,kind,price,sent_at) VALUES(?,?,?,?)",
            (variant_id, kind, price, now()),
        )
