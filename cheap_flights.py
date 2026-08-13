from __future__ import annotations

import config
import currency
from locations import SOUTH_AMERICA
from notify import _fmt_date, _fmt_price, send_message


def filter_cheap(offers: list[dict]) -> list[dict]:
    cheap = []
    for offer in offers:
        if offer.get("price") is None:
            continue
        price_eur = currency.convert(offer["price"], offer["currency"], "EUR")
        if price_eur is not None and price_eur < config.MAX_PRICE_EUR:
            cheap.append(offer)
    cheap.sort(key=lambda o: o["price"])
    return cheap[: config.MAX_RESULTS_PER_ROUTE]


def format_cheap_offers(offers: list[dict]) -> str | None:
    if not offers:
        return None
    lines = [f"💸 Günstige Flüge unter {config.MAX_PRICE_EUR:.0f}€ (alle Wochentage)\n"]
    for offer in offers:
        loc = SOUTH_AMERICA.get(offer["destination"])
        label = f"{loc['flag']} {loc['city']}" if loc else offer["destination"]
        dates = f"{_fmt_date(offer['flight_date'])}→{_fmt_date(offer['return_date'])}"
        pattern = " (Do→Mo)" if offer.get("weekday_match") else ""
        lines.append(f"{label} ({offer['origin']}): {_fmt_price(offer['price'], offer['currency'])} · {dates}{pattern}")
    return "\n".join(lines)


def send_cheap_flights(offers: list[dict]) -> None:
    text = format_cheap_offers(filter_cheap(offers))
    if text is not None:
        send_message(text)
