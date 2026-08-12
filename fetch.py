from __future__ import annotations

import logging
from datetime import datetime, timezone

import requests

import config

logger = logging.getLogger(__name__)


def _matches_preferred_pattern(flight_date: str, return_date: str | None) -> bool:
    if not flight_date or not return_date:
        return False
    try:
        depart_ok = datetime.strptime(flight_date, "%Y-%m-%d").weekday() == config.PREFERRED_DEPART_WEEKDAY
        return_ok = datetime.strptime(return_date, "%Y-%m-%d").weekday() == config.PREFERRED_RETURN_WEEKDAY
    except ValueError:
        return False
    return depart_ok and return_ok


def fetch_route(origin: str, destination: str) -> list[dict]:
    params = {
        "origin": origin,
        "destination": destination if destination != "anywhere" else "-",
        "currency": config.CURRENCY,
    }
    if config.DEPART_DATE:
        params["depart_date"] = config.DEPART_DATE

    headers = {"X-Access-Token": config.TRAVELPAYOUTS_TOKEN}

    try:
        response = requests.get(
            config.TRAVELPAYOUTS_API_URL, params=params, headers=headers, timeout=config.REQUEST_TIMEOUT
        )
        response.raise_for_status()
    except requests.RequestException:
        logger.exception("Travelpayouts-Anfrage fehlgeschlagen fuer %s -> %s", origin, destination)
        return []

    payload = response.json()
    if not payload.get("success"):
        logger.warning(
            "Travelpayouts meldet Fehler fuer %s -> %s: %s", origin, destination, payload.get("error")
        )
        return []

    fetched_at = datetime.now(timezone.utc).isoformat()
    results = []
    for dest_code, entries in payload.get("data", {}).items():
        for entry in entries.values():
            flight_date = (entry.get("departure_at") or "")[:10]
            return_date = (entry.get("return_at") or "")[:10] or None
            results.append(
                {
                    "origin": origin,
                    "destination": dest_code,
                    "price": entry.get("price"),
                    "currency": config.CURRENCY,
                    "flight_date": flight_date,
                    "return_date": return_date,
                    "airlines": entry.get("airline", ""),
                    "booking_token": None,
                    "deep_link": None,
                    "fetched_at": fetched_at,
                    "weekday_match": _matches_preferred_pattern(flight_date, return_date),
                }
            )

    results.sort(key=lambda r: r["price"] if r["price"] is not None else float("inf"))
    return results[: config.MAX_RESULTS_PER_ROUTE]


def fetch_all() -> list[dict]:
    if not config.TRAVELPAYOUTS_TOKEN:
        raise RuntimeError("TRAVELPAYOUTS_TOKEN ist nicht gesetzt (siehe .env)")

    all_results = []
    for origin in config.ORIGINS:
        for destination in config.DESTINATIONS:
            route_results = fetch_route(origin, destination)
            logger.info("%d Angebote fuer %s -> %s", len(route_results), origin, destination)
            all_results.extend(route_results)
    return all_results
