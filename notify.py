from __future__ import annotations

import logging
import time
from datetime import datetime

import requests

import config
from analyze import Alert
from locations import SOUTH_AMERICA

logger = logging.getLogger(__name__)

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"
EXCHANGE_RATE_URL = "https://api.frankfurter.app/latest"
EXCHANGE_RATE_TTL_SECONDS = 3600

CURRENCY_SYMBOLS = {"BRL": "R$", "EUR": "€"}
SECONDARY_CURRENCY = "EUR" if config.CURRENCY == "BRL" else "BRL"

GERMAN_WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

_rate_cache: dict[str, tuple[float, float]] = {}


def _symbol(currency: str) -> str:
    return CURRENCY_SYMBOLS.get(currency, currency)


def get_conversion_rate(from_currency: str, to_currency: str) -> float | None:
    if from_currency == to_currency:
        return 1.0

    cache_key = f"{from_currency}->{to_currency}"
    cached = _rate_cache.get(cache_key)
    if cached and time.time() - cached[1] < EXCHANGE_RATE_TTL_SECONDS:
        return cached[0]

    rate = None
    for attempt in range(2):
        try:
            response = requests.get(
                EXCHANGE_RATE_URL,
                params={"from": from_currency, "to": to_currency},
                timeout=5,
            )
            response.raise_for_status()
            rate = response.json()["rates"][to_currency]
            break
        except (requests.RequestException, KeyError):
            if attempt == 0:
                continue
            logger.warning("Wechselkurs %s -> %s konnte nicht abgerufen werden", from_currency, to_currency)

    if rate is None:
        return cached[0] if cached else None

    _rate_cache[cache_key] = (rate, time.time())
    return rate


def _fmt_price(amount: float, currency: str) -> str:
    text = f"{_symbol(currency)} {amount:.0f}"
    rate = get_conversion_rate(currency, SECONDARY_CURRENCY)
    if rate is not None:
        text += f" / {_symbol(SECONDARY_CURRENCY)} {amount * rate:.0f}"
    return text


def _fmt_date(date_str: str | None) -> str:
    if not date_str:
        return "?"
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return date_str
    return f"{GERMAN_WEEKDAYS[dt.weekday()]} {dt.strftime('%d.%m.')}"


def format_alert(alert: Alert) -> str:
    loc = SOUTH_AMERICA.get(alert.destination)
    label = f"{loc['flag']} {loc['city']}" if loc else alert.destination

    price_line = f"💰 {_fmt_price(alert.price, alert.currency)}"
    if alert.average:
        drop_percent = (1 - alert.price / alert.average) * 100
        price_line += f" (Ø14T: {_fmt_price(alert.average, alert.currency)}, -{drop_percent:.0f}%)"

    date_line = f"📅 {_fmt_date(alert.flight_date)}"
    if alert.return_date:
        date_line += f" → {_fmt_date(alert.return_date)}"
    date_line += "  ✅ Do–Mo" if alert.weekday_match else "  ⚠️ abweichend"

    lines = [
        f"✈️ {label} ({alert.destination}) ab {alert.origin}",
        price_line,
        date_line,
    ]
    if alert.airlines:
        lines.append(f"🛫 {alert.airlines}")
    if alert.deep_link:
        lines.append(alert.deep_link)
    return "\n".join(lines)


def send_message(text: str) -> bool:
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        logger.warning("Telegram nicht konfiguriert, Nachricht wird nicht gesendet")
        return False

    url = TELEGRAM_API_URL.format(token=config.TELEGRAM_BOT_TOKEN)
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": text,
        "disable_web_page_preview": False,
    }
    try:
        response = requests.post(url, json=payload, timeout=config.REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException:
        logger.exception("Telegram-Nachricht konnte nicht gesendet werden")
        return False
    return True


def send_alerts(alerts: list[Alert]) -> None:
    for alert in alerts:
        send_message(format_alert(alert))
