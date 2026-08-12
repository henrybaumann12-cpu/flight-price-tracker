from __future__ import annotations

import logging
from datetime import datetime

import requests

import config
import currency
from analyze import Alert
from locations import SOUTH_AMERICA

logger = logging.getLogger(__name__)

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"
SECONDARY_CURRENCY = "EUR" if config.CURRENCY == "BRL" else "BRL"

GERMAN_WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def _fmt_price(amount: float, currency_code: str) -> str:
    text = f"{currency.symbol(currency_code)} {amount:.0f}"
    converted = currency.convert(amount, currency_code, SECONDARY_CURRENCY)
    if converted is not None:
        text += f" / {currency.symbol(SECONDARY_CURRENCY)} {converted:.0f}"
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

    drop_percent = (1 - alert.price / alert.average) * 100 if alert.average else None
    price_line = f"💰 {_fmt_price(alert.price, alert.currency)}"
    if drop_percent is not None:
        price_line += f"  (-{drop_percent:.0f}%)"

    date_line = f"📅 {_fmt_date(alert.flight_date)}"
    if alert.return_date:
        date_line += f" → {_fmt_date(alert.return_date)}"
    date_line += " ✅" if alert.weekday_match else " ⚠️"

    return "\n".join(
        [
            f"🚨 {label} ab {alert.origin}",
            price_line,
            date_line,
        ]
    )


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
