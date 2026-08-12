from __future__ import annotations

import logging
from dataclasses import dataclass

import config
import currency
import db

logger = logging.getLogger(__name__)


@dataclass
class Alert:
    origin: str
    destination: str
    price: float
    currency: str
    flight_date: str
    return_date: str | None
    airlines: str
    deep_link: str | None
    average: float | None
    reason: str
    weekday_match: bool


def evaluate_offer(conn, offer: dict) -> Alert | None:
    origin, destination, price = offer["origin"], offer["destination"], offer["price"]
    if price is None:
        return None

    history = db.get_recent_prices(conn, origin, destination, config.ROLLING_WINDOW_DAYS)
    # history enthaelt bereits den soeben eingefuegten Preis -> fuer den Vergleich ausschliessen
    history = [p for p in history if p != price] or history
    average = sum(history) / len(history) if history else None

    reason = None
    if average is not None and len(history) >= config.MIN_SAMPLES_FOR_AVERAGE:
        if price <= average * (1 - config.DROP_PERCENT):
            reason = (
                f"{config.DROP_PERCENT * 100:.0f}% unter dem "
                f"{config.ROLLING_WINDOW_DAYS}-Tage-Durchschnitt ({average:.2f} {offer['currency']})"
            )

    if config.FIXED_THRESHOLD > 0 and price <= config.FIXED_THRESHOLD:
        threshold_reason = f"unter Fixschwelle von {config.FIXED_THRESHOLD:.2f} {offer['currency']}"
        reason = f"{reason} und {threshold_reason}" if reason else threshold_reason

    if reason is None:
        return None

    if config.MAX_PRICE_EUR > 0:
        price_eur = currency.convert(price, offer["currency"], "EUR")
        if price_eur is None or price_eur >= config.MAX_PRICE_EUR:
            logger.info(
                "Alert fuer %s -> %s unterdrueckt (%.2f %s ueber %s EUR Obergrenze)",
                origin, destination, price, offer["currency"], config.MAX_PRICE_EUR,
            )
            return None

    return Alert(
        origin=origin,
        destination=destination,
        price=price,
        currency=offer["currency"],
        flight_date=offer["flight_date"],
        return_date=offer.get("return_date"),
        airlines=offer.get("airlines", ""),
        deep_link=offer.get("deep_link"),
        average=average,
        reason=reason,
        weekday_match=offer.get("weekday_match", False),
    )


def find_alerts(conn, offers: list[dict]) -> list[Alert]:
    alerts = []
    for offer in offers:
        alert = evaluate_offer(conn, offer)
        if alert is None:
            continue
        if db.was_recently_alerted(
            conn, alert.origin, alert.destination, alert.flight_date, config.ALERT_COOLDOWN_HOURS
        ):
            logger.info(
                "Alert fuer %s -> %s am %s unterdrueckt (Cooldown aktiv)",
                alert.origin, alert.destination, alert.flight_date,
            )
            continue
        alerts.append(alert)
    return alerts
