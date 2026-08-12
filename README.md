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

- `fetch.py` – Travelpayouts-API-Abfrage (`v1/prices/cheap`)
- `db.py` – SQLite-Speicherung (Preisverlauf + gesendete Alarme)
- `analyze.py` – Preistrend-/Ausreißer-Erkennung
- `notify.py` – Telegram-Benachrichtigung (kompaktes Format mit Länder-Flaggen-Emoji)
- `locations.py` – IATA-Code → Stadt/Land/Flagge-Mapping für die Südamerika-Ziele
- `main.py` – orchestriert fetch → db → analyze → notify

## Ziele

Standardmäßig werden 12 Ziele in Südamerika geprüft (siehe `locations.py`):
Buenos Aires 🇦🇷, Santiago 🇨🇱, Lima 🇵🇪, Cusco 🇵🇪, Bogotá 🇨🇴, Cartagena 🇨🇴, Quito 🇪🇨,
Montevideo 🇺🇾, Asunción 🇵🇾, La Paz 🇧🇴, Caracas 🇻🇪, Georgetown 🇬🇾. Anpassbar über
`DESTINATIONS` in `.env` (Komma-getrennte IATA-Codes, oder `anywhere` für alle Ziele ab Origin).

## Reisemuster (Do → Mo)

Bevorzugt wird Abflug **Donnerstag**, Rückflug **Montag** (`PREFERRED_DEPART_WEEKDAY` /
`PREFERRED_RETURN_WEEKDAY` in `config.py`). Die Travelpayouts-API kann aber nicht nach Wochentag
gefiltert werden – es wird stattdessen breit nach den günstigsten gecachten Fares pro Ziel gesucht
und jedes Ergebnis mit ✅ (Muster passt) oder ⚠️ (abweichende Tage) markiert. Guenstige Abweichungen
werden also weiterhin gemeldet, nur eben entsprechend gekennzeichnet.

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

- der Preis ≥ `DROP_PERCENT` (Standard 15 %) unter dem gleitenden Durchschnitt der letzten
  `ROLLING_WINDOW_DAYS` Tage für dieselbe Route liegt, **und/oder**
- der Preis unter `FIXED_THRESHOLD` liegt (0 = deaktiviert).

Um Spam zu vermeiden, wird pro Route+Abflugdatum maximal alle `ALERT_COOLDOWN_HOURS` Stunden
ein Alarm gesendet (`alerts_sent`-Tabelle in SQLite).

## Datenbank

SQLite-Datei unter `DB_PATH` (Standard `flights.db`) mit zwei Tabellen:

- `price_history` – jeder abgefragte Preis mit Zeitstempel
- `alerts_sent` – Protokoll gesendeter Alarme (für Cooldown)
