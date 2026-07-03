import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import get_settings
from app.ingest.rss_scanner import run_scan
from app.ingest.x_sync import run_x_sync

log = logging.getLogger("scheduler")


def start_scheduler() -> BackgroundScheduler | None:
    s = get_settings()
    if not s.scan_enabled:
        log.info("scheduler disabled (SCAN_ENABLED=false)")
        return None
    sched = BackgroundScheduler()
    sched.add_job(run_scan, CronTrigger.from_crontab(s.scan_cron), id="rss_scan")
    sched.add_job(run_x_sync, "interval", hours=s.x_sync_interval_hours, id="x_sync")
    sched.start()
    log.info("scheduler started")
    return sched
