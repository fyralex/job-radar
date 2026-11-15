"""The scheduled scraper: `python -m job_radar.worker`.

Runs in its own container so gunicorn's web workers never schedule scrapes.
Every `CHECK_SECONDS` it reads the interval from settings and runs a full
scrape when one is due, so a settings change applies without a restart.
"""

from __future__ import annotations

import logging
import signal
import threading
from types import FrameType

from job_radar.config import Config
from job_radar.coordination import make_locks
from job_radar.db import make_engine, make_session_factory, session_scope
from job_radar.models import utcnow
from job_radar.services.refresh import run_scrape, scrape_due
from job_radar.services.settings_repo import get_settings

CHECK_SECONDS = 300
logger = logging.getLogger("job_radar.worker")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    config = Config.from_env()
    factory = make_session_factory(make_engine(config.database_url))
    locks = make_locks(config.redis_url)
    stop = threading.Event()

    def _stop(_signum: int, _frame: FrameType | None) -> None:
        stop.set()

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    logger.info("worker started; checking every %ss", CHECK_SECONDS)
    while not stop.is_set():
        try:
            with session_scope(factory) as session:
                settings = get_settings(session)
                due = scrape_due(
                    settings.last_full_scrape_at, settings.scrape_interval_hours, utcnow()
                )
            if due:
                summary = run_scrape(
                    factory, config.contact_url, config.scrape_workers, locks=locks
                )
                if summary:
                    logger.info(
                        "scraped %s boards (%s failed, %s skipped), %s postings",
                        summary.boards,
                        summary.failed,
                        summary.skipped,
                        summary.postings,
                    )
                else:
                    logger.info("scrape due, but another run holds the lock (or Redis is down)")
        except Exception:
            logger.exception("scheduled scrape failed")
        stop.wait(CHECK_SECONDS)


if __name__ == "__main__":
    main()
