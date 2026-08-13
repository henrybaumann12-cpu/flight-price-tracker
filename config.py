from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from locations import SOUTH_AMERICA

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _list_env(name: str, default: str) -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def _int_env(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _float_env(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


# --- Travelpayouts (Aviasales) Data API ---
TRAVELPAYOUTS_TOKEN = os.getenv("TRAVELPAYOUTS_TOKEN", "")
TRAVELPAYOUTS_API_URL = "https://api.travelpayouts.com/v1/prices/cheap"

# --- Routen ---
ORIGINS = _list_env("ORIGINS", "GRU,CGH")
# IATA-Codes, Standard: 12 Ziele in Suedamerika (siehe locations.py), oder "anywhere"
# fuer Suche ueber alle Ziele ab Origin
DESTINATIONS = _list_env("DESTINATIONS", ",".join(SOUTH_AMERICA.keys()))
CURRENCY = os.getenv("CURRENCY", "BRL")

MAX_RESULTS_PER_ROUTE = _int_env("MAX_RESULTS_PER_ROUTE", 20)

# Bevorzugtes Reisemuster: Abflug Donnerstag, Rueckflug Montag. Wird ueber den
# Kalender-Endpoint (v1/prices/calendar, ein ganzer Monat mit vielen Abflugterminen
# pro Aufruf) gesucht und client-seitig gefiltert, rotierend ueber SEARCH_MONTHS_AHEAD
# Monate (ein anderer Monat pro Stunde, siehe fetch.select_target_month).
PREFERRED_DEPART_WEEKDAY = 3  # Montag=0 ... Donnerstag=3
PREFERRED_RETURN_WEEKDAY = 0  # Montag=0
SEARCH_MONTHS_AHEAD = _int_env("SEARCH_MONTHS_AHEAD", 6)
# Erstmal nur Do->Mo-Kombinationen melden (harter Filter), Abweichungen werden
# weiterhin gespeichert (fuer die Preishistorie), aber nicht gemeldet
REQUIRE_PREFERRED_PATTERN = os.getenv("REQUIRE_PREFERRED_PATTERN", "true").lower() == "true"

# --- Preisalarm ---
ROLLING_WINDOW_DAYS = _int_env("ROLLING_WINDOW_DAYS", 14)
DROP_PERCENT = _float_env("DROP_PERCENT", 0.15)   # 15% unter gleitendem Durchschnitt
FIXED_THRESHOLD = _float_env("FIXED_THRESHOLD", 0)  # 0 = deaktiviert
MIN_SAMPLES_FOR_AVERAGE = _int_env("MIN_SAMPLES_FOR_AVERAGE", 3)
ALERT_COOLDOWN_HOURS = _int_env("ALERT_COOLDOWN_HOURS", 20)
# Harte Obergrenze in EUR: nur Preise darunter werden gemeldet, 0 = deaktiviert
MAX_PRICE_EUR = _float_env("MAX_PRICE_EUR", 400)

# --- Telegram ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# --- Sonstiges ---
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "flights.db"))
LOG_PATH = os.getenv("LOG_PATH", str(BASE_DIR / "flight_tracker.log"))
REQUEST_TIMEOUT = _int_env("REQUEST_TIMEOUT", 20)
