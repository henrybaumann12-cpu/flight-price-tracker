import logging

import config
import db
import fetch
import notify
from analyze import find_alerts


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=[
            logging.FileHandler(config.LOG_PATH),
            logging.StreamHandler(),
        ],
    )


def main() -> None:
    setup_logging()
    logger = logging.getLogger("main")

    db.init_db()

    try:
        offers = fetch.fetch_all()
    except RuntimeError as exc:
        logger.error(str(exc))
        return

    if not offers:
        logger.info("Keine Angebote erhalten, Lauf wird beendet")
        return

    with db.get_connection() as conn:
        for offer in offers:
            if offer["price"] is not None:
                db.insert_price(conn, offer)

        alerts = find_alerts(conn, offers)
        for alert in alerts:
            db.record_alert(conn, alert.origin, alert.destination, alert.flight_date, alert.price)

    logger.info("%d Angebote gespeichert, %d Preisalarme ausgeloest", len(offers), len(alerts))
    notify.send_alerts(alerts)


if __name__ == "__main__":
    main()
