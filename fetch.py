from __future__ import annotations

import logging
from datetime import datetime, timezone

import requests

import config

logger = logging.getLogger(__name__)

CALENDAR_API_URL = "https://api.travelpayouts.com/v1/prices/calendar"


def matches_preferred_pattern(flight_date: str, return_date: str | None) -> bool:
    if not flight_date or not return_date:
        return False
    try:
        depart_ok = datetime.strptime(flight_date, "%Y-%m-%d").weekday() == config.PREFERRED_DEPART_WEEKDAY
        return_ok = datetime.strptime(return_date, "%Y-%m-%d").weekday() == config.PREFERRED_RETURN_WEEKDAY
    except ValueError:
        return False
    return depart_ok and return_ok


def upcoming_months(months_ahead: int) -> list[str]:
    today = datetime.now(timezone.utc).date()
    months = []
    year, month = today.year, today.month
    for _ in range(months_ahead):
        months.append(f"{year:04d}-{month:02d}")
        month += 1
        if month > 12:
            month = 1
            year += 1
    return months


def select_target_month() -> str:
    """Waehlt deterministisch einen Monat pro Stunde aus, rotierend ueber den Suchzeitraum."""
    months = upcoming_months(config.SEARCH_MONTHS_AHEAD)
    hours_since_epoch = int(datetime.now(timezone.utc).timestamp() // 3600)
    return months[hours_since_epoch % len(months)]


def fetch_calendar_route(origin: str, destination: str, year_month: str) -> list[dict]:
    params = {
        "origin": origin,
        "destination": destination,
        "depart_date": year_month,
        "currency": config.CURRENCY,
    }
    headers = {"X-Access-Token": config.TRAVELPAYOUTS_TOKEN}

    try:
        response = requests.get(
            CALENDAR_API_URL, params=params, headers=headers, timeout=config.REQUEST_TIMEOUT
        )
        response.raise_for_status()
    except requests.RequestException:
        logger.exception("Travelpayouts-Kalenderanfrage fehlgeschlagen fuer %s -> %s", origin, destination)
        return []

    payload = response.json()
    if not payload.get("success", True):
        logger.warning(
            "Travelpayouts meldet Fehler fuer %s -> %s: %s", origin, destination, payload.get("error")
        )
        return []

    fetched_at = datetime.now(timezone.utc).isoformat()
    results = []
    for entry in payload.get("data", {}).values():
        flight_date = (entry.get("departure_at") or "")[:10]
        return_date = (entry.get("return_at") or "")[:10] or None

        if config.REQUIRE_PREFERRED_PATTERN and not matches_preferred_pattern(flight_date, return_date):
            continue

        results.append(
            {
                "origin": origin,
                "destination": destination,
                "price": entry.get("price"),
                "currency": config.CURRENCY,
                "flight_date": flight_date,
                "return_date": return_date,
                "airlines": entry.get("airline", ""),
                "booking_token": None,
                "deep_link": None,
                "fetched_at": fetched_at,
                "weekday_match": matches_preferred_pattern(flight_date, return_date),
            }
        )

    results.sort(key=lambda r: r["price"] if r["price"] is not None else float("inf"))
    return results[: config.MAX_RESULTS_PER_ROUTE]


def fetch_all() -> list[dict]:
    if not config.TRAVELPAYOUTS_TOKEN:
        raise RuntimeError("TRAVELPAYOUTS_TOKEN ist nicht gesetzt (siehe .env)")

    year_month = select_target_month()
    logger.info("Ziel-Monat diese Stunde: %s", year_month)

    all_results = []
    for origin in config.ORIGINS:
        for destination in config.DESTINATIONS:
            route_results = fetch_calendar_route(origin, destination, year_month)
            logger.info("%d Do->Mo-Angebote fuer %s -> %s (%s)", len(route_results), origin, destination, year_month)
            all_results.extend(route_results)
    return all_results
