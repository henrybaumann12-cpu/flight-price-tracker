from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    origin TEXT NOT NULL,
    destination TEXT NOT NULL,
    price REAL NOT NULL,
    currency TEXT NOT NULL,
    flight_date TEXT,
    return_date TEXT,
    airlines TEXT,
    booking_token TEXT,
    deep_link TEXT,
    fetched_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_price_history_route
    ON price_history (origin, destination, fetched_at);

CREATE TABLE IF NOT EXISTS alerts_sent (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    origin TEXT NOT NULL,
    destination TEXT NOT NULL,
    flight_date TEXT,
    price REAL NOT NULL,
    sent_at TEXT NOT NULL
);
"""


@contextmanager
def get_connection():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(SCHEMA)


def insert_price(conn, record: dict) -> None:
    conn.execute(
        """
        INSERT INTO price_history
            (origin, destination, price, currency, flight_date, return_date,
             airlines, booking_token, deep_link, fetched_at)
        VALUES (:origin, :destination, :price, :currency, :flight_date, :return_date,
                :airlines, :booking_token, :deep_link, :fetched_at)
        """,
        record,
    )


def get_recent_prices(conn, origin: str, destination: str, days: int) -> list[float]:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    rows = conn.execute(
        """
        SELECT price FROM price_history
        WHERE origin = ? AND destination = ? AND fetched_at >= ?
        """,
        (origin, destination, since),
    ).fetchall()
    return [row["price"] for row in rows]


def was_recently_alerted(conn, origin: str, destination: str, flight_date: str, cooldown_hours: int) -> bool:
    since = (datetime.now(timezone.utc) - timedelta(hours=cooldown_hours)).isoformat()
    row = conn.execute(
        """
        SELECT 1 FROM alerts_sent
        WHERE origin = ? AND destination = ? AND flight_date = ? AND sent_at >= ?
        LIMIT 1
        """,
        (origin, destination, flight_date, since),
    ).fetchone()
    return row is not None


def record_alert(conn, origin: str, destination: str, flight_date: str, price: float) -> None:
    conn.execute(
        """
        INSERT INTO alerts_sent (origin, destination, flight_date, price, sent_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (origin, destination, flight_date, price, datetime.now(timezone.utc).isoformat()),
    )
