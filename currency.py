from __future__ import annotations

import logging
import time

import requests

import config

logger = logging.getLogger(__name__)

EXCHANGE_RATE_URL = "https://api.frankfurter.app/latest"
EXCHANGE_RATE_TTL_SECONDS = 3600

CURRENCY_SYMBOLS = {"BRL": "R$", "EUR": "€"}

_rate_cache: dict[str, tuple[float, float]] = {}


def symbol(currency: str) -> str:
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


def convert(amount: float, from_currency: str, to_currency: str) -> float | None:
    rate = get_conversion_rate(from_currency, to_currency)
    return amount * rate if rate is not None else None
