# Flight Price Tracker (GRU/CGH)

Fragt Flugpreise ab São Paulo (GRU/CGH) über die [Travelpayouts (Aviasales) Data API](https://support.travelpayouts.com/hc/en-us/articles/203956163-Aviasales-Data-API)
ab, speichert sie in SQLite und meldet über Telegram, wenn ein Preis ungewöhnlich günstig ist
(unter dem gleitenden 14-Tage-Durchschnitt und/oder unter einem Fixschwellenwert).

> **Hinweis zur API-Wahl:** Ursprünglich war die Kiwi.com Tequila API vorgesehen, diese vergibt
> aber seit Mai 2024 keine neuen Self-Service-Zugänge mehr an Einzelentwickler
> ("invitation only", siehe [Kiwi.com-Ankündigung](https://media.kiwi.com/articles-and-interviews/better-for-business-kiwi-com-takes-a-new-approach-to-partnerships/)).
> Travelpayouts/Aviasales bietet eine offene, kostenlose Self-Service-Registrierung und eignet
> sich gut für genau diesen Use Case (Preisalarm auf Basis zwischengespeicherter Fund-Daten).

## Struktur

- `fetch.py` – Travelpayouts-API-Abfrage (`v1/prices/calendar`)
- `db.py` – SQLite-Speicherung (Preisverlauf + gesendete Alarme)
- `analyze.py` – Preistrend-/Ausreißer-Erkennung
- `notify.py` – Telegram-Benachrichtigung (kompaktes Format mit Länder-Flaggen-Emoji)
- `locations.py` – IATA-Code → Stadt/Land/Flagge-Mapping für die Südamerika-Ziele
- `digest.py` – 2-stündliche Sammel-Nachricht aller Do→Mo-Flüge unter `MAX_PRICE_EUR`
- `cheap_flights.py` – stündliche Sammel-Nachricht aller Flüge unter `MAX_PRICE_EUR`,
  **ohne** Do→Mo-Zwang (jeder Wochentag zählt, nur der Preis muss stimmen)
- `main.py` – orchestriert fetch → db → analyze → notify (+ cheap_flights)

## Drei Arten von Telegram-Nachrichten

1. **Preisalarm** (`main.py`, stündlich): Do→Mo, unter `MAX_PRICE_EUR`, **und** deutlich unter
   dem historischen Durchschnitt der Route (`DROP_PERCENT`/`FIXED_THRESHOLD`) — die strengste Stufe.
2. **Digest** (`digest.py`, alle 2h): alle aktuell gecachten Do→Mo-Flüge unter `MAX_PRICE_EUR`,
   unabhängig vom Durchschnittsvergleich.
3. **Cheap Flights** (`cheap_flights.py`, stündlich, Teil von `main.py`): alle Flüge unter
   `MAX_PRICE_EUR` **ohne** Wochentag-Einschränkung — reiner Preis-Cutoff, jeder Fund wird mit
   "(Do→Mo)" markiert, falls er zufällig das Muster trifft. Diese Angebote werden **nicht** in
   der Datenbank gespeichert (nur die Do→Mo-Treffer fließen in die Preishistorie ein, damit der
   Durchschnittsvergleich nicht durch andere Wochentag-Muster verzerrt wird).

## Ziele

Standardmäßig werden 12 Ziele in Südamerika geprüft (siehe `locations.py`):
Buenos Aires 🇦🇷, Santiago 🇨🇱, Lima 🇵🇪, Cusco 🇵🇪, Bogotá 🇨🇴, Cartagena 🇨🇴, Quito 🇪🇨,
Montevideo 🇺🇾, Asunción 🇵🇾, La Paz 🇧🇴, Caracas 🇻🇪, Georgetown 🇬🇾. Anpassbar über
`DESTINATIONS` in `.env` (Komma-getrennte IATA-Codes, oder `anywhere` für alle Ziele ab Origin).

## Reisemuster (Do → Mo)

Erforderlich ist Abflug **Donnerstag**, Rückflug **Montag** (`PREFERRED_DEPART_WEEKDAY` /
`PREFERRED_RETURN_WEEKDAY` in `config.py`).

**Wichtige Erkenntnis:** Der einfache "cheapest price"-Endpoint (`v1/prices/cheap`) liefert nur
einen zufälligen Cache-Treffer pro Ziel (das, was zufällig andere Nutzer zuletzt gesucht haben) –
in über 200 Testabfragen kam dabei **kein einziges Mal** eine Do→Mo-Kombination vor, exakte
Tagesangaben lieferten sogar durchgehend 0 Treffer. Daher nutzt `fetch.py` stattdessen den
**Kalender-Endpoint** (`v1/prices/calendar`), der für einen ganzen Monat viele einzelne
Abflugtermine mit echten Daten zurückgibt (~50-70 pro Monat/Route). Daraus werden client-seitig
die tatsächlichen Do→Mo-Kombinationen herausgefiltert (`fetch.matches_preferred_pattern`).

Da ein Monatsaufruf pro Route relativ "teuer" ist, wird pro Stunde nur **ein** Zielmonat aus den
kommenden `SEARCH_MONTHS_AHEAD` Monaten abgefragt (rotierend, `fetch.select_target_month`) – so
werden alle Monate im Suchzeitraum nach und nach abgedeckt, ohne pro Lauf zu viele API-Calls zu
brauchen. Mit `REQUIRE_PREFERRED_PATTERN=true` (Standard) werden nur Do→Mo-Treffer überhaupt
gespeichert und gemeldet. Zum Deaktivieren (dann zaehlen auch andere Wochentag-Kombinationen):
`REQUIRE_PREFERRED_PATTERN=false` in `.env` setzen.

## Setup

```bash
cd flight-price-tracker
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

`.env` ausfüllen:

- `TRAVELPAYOUTS_TOKEN` – auf [travelpayouts.com](https://www.travelpayouts.com/) kostenlos registrieren
  (normaler Account, kein Invite nötig), dann Token unter
  [travelpayouts.com/programs/100/tools/api](https://www.travelpayouts.com/programs/100/tools/api) holen
- `TELEGRAM_BOT_TOKEN` – über [@BotFather](https://t.me/BotFather) einen Bot anlegen
- `TELEGRAM_CHAT_ID` – eigene Chat-ID, z. B. via [@userinfobot](https://t.me/userinfobot) ermitteln,
  oder Bot anschreiben und `https://api.telegram.org/bot<TOKEN>/getUpdates` aufrufen
- `DESTINATIONS` – Komma-getrennte IATA-Codes (Standard: 12 Südamerika-Ziele, siehe oben) oder
  `anywhere` für eine Suche über alle Ziele ab dem jeweiligen Origin (nutzt intern `destination=-`)

Manuell testen:

```bash
python3 main.py
```

Beim ersten Lauf gibt es noch keinen Durchschnitt (siehe `MIN_SAMPLES_FOR_AVERAGE`), erst nach
ein paar Läufen mit historischen Daten schlägt der Preisvergleich zu.

## Als Cronjob einrichten (mehrmals täglich)

Aktuell eingerichtet: alle 4 Stunden (6× täglich: 00/04/08/12/16/20 Uhr).

```bash
crontab -e
```

```
0 */4 * * * cd /Users/henrybaumann/flight-price-tracker && /Users/henrybaumann/flight-price-tracker/.venv/bin/python main.py >> /Users/henrybaumann/flight-price-tracker/cron.log 2>&1
```

**macOS-Hinweis:** `cron` benötigt evtl. "Full Disk Access" in Systemeinstellungen → Datenschutz &
Sicherheit, sonst laufen die Jobs lautlos nicht.

Alternative auf macOS: ein `launchd`-Job (`~/Library/LaunchAgents/com.user.flighttracker.plist`)
mit `StartCalendarInterval`-Einträgen, falls Cron durch Energiesparmodus ausgesetzt wird.

## Preisalarm-Logik

Ein Angebot löst einen Alarm aus, wenn (siehe `analyze.py`):

1. der Preis ≥ `DROP_PERCENT` (Standard 15 %) unter dem gleitenden Durchschnitt der letzten
   `ROLLING_WINDOW_DAYS` Tage für dieselbe Route liegt, **und/oder** unter `FIXED_THRESHOLD`
   liegt (0 = deaktiviert), **und zusätzlich**
2. der Preis umgerechnet unter `MAX_PRICE_EUR` liegt (Standard 400 €, 0 = deaktiviert) —
   harte Obergrenze, unabhängig vom Rabatt.

Um Spam zu vermeiden, wird pro Route+Abflugdatum maximal alle `ALERT_COOLDOWN_HOURS` Stunden
ein Alarm gesendet (`alerts_sent`-Tabelle in SQLite).

## Digest (`digest.py`)

Zusätzlich zum Preisalarm gibt es alle 2 Stunden (12×/Tag) eine Sammel-Nachricht mit **allen**
aktuell gecachten Do→Mo-Flügen unter `MAX_PRICE_EUR` — unabhängig davon, ob sie auch den
Rabatt-Check (Preisalarm-Logik oben) bestehen. Der Preisalarm-Check (`main.py`) selbst läuft
weiterhin stündlich (24×/Tag). Im GitHub-Actions-Workflow ist das über eine Stunden-Prüfung
(`date -u +%H`, gerade Stunde → Digest) im selben stündlichen Lauf umgesetzt, kein separater
Cronjob nötig.

`currency.py` holt den Live-Wechselkurs (ECB via frankfurter.app) für die 300€-Grenze und für
die zweite Währung in den Nachrichten.

## Datenbank

SQLite-Datei unter `DB_PATH` (Standard `flights.db`) mit zwei Tabellen:

- `price_history` – jeder abgefragte Preis mit Zeitstempel
- `alerts_sent` – Protokoll gesendeter Alarme (für Cooldown)
