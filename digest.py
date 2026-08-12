from __future__ import annotations

import logging
import sqlite3

import config
import currency
from fetch import matches_preferred_pattern
from locations import SOUTH_AMERICA
from notify import _fmt_date, _fmt_price, send_message

logger = logging.getLogger(__name__)


def build_digest() -> str | None:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row

    destinations = list(SOUTH_AMERICA.keys())
    rows = conn.execute(
        """
        WITH latest AS (
            SELECT origin, destination, MAX(fetched_at) AS latest_fetch
            FROM price_history WHERE destination IN ({placeholders}) GROUP BY origin, destination
        )
        SELECT p.origin, p.destination, MIN(p.price) AS price, p.currency, p.flight_date, p.return_date
        FROM price_history p
        JOIN latest l ON p.origin = l.origin AND p.destination = l.destination AND p.fetched_at = l.latest_fetch
        GROUP BY p.origin, p.destination
        ORDER BY price ASC
        """.format(placeholders=",".join("?" * len(destinations)))
        , destinations,
    ).fetchall()
    conn.close()

    under_cap = []
    for row in rows:
        if config.REQUIRE_PREFERRED_PATTERN and not matches_preferred_pattern(
            row["flight_date"], row["return_date"]
        ):
            continue
        price_eur = currency.convert(row["price"], row["currency"], "EUR")
        if price_eur is not None and price_eur < config.MAX_PRICE_EUR:
            under_cap.append(row)

    if not under_cap:
        return None

    lines = [f"📋 Flüge unter {config.MAX_PRICE_EUR:.0f}€ (Stand jetzt)\n"]
    for row in under_cap:
        loc = SOUTH_AMERICA.get(row["destination"])
        label = f"{loc['flag']} {loc['city']}" if loc else row["destination"]
        dates = f"{_fmt_date(row['flight_date'])}→{_fmt_date(row['return_date'])}"
        lines.append(f"{label} ({row['origin']}): {_fmt_price(row['price'], row['currency'])} · {dates}")
    return "\n".join(lines)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    text = build_digest()
    if text is None:
        logger.info("Keine Angebote unter %s EUR, kein Digest gesendet", config.MAX_PRICE_EUR)
        return
    send_message(text)


if __name__ == "__main__":
    main()
