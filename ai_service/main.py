import os
import time
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

from graph.agent import build_graph


def parse_run_times(value: str) -> list[tuple[int, int]]:
    times = []
    for part in value.split(","):
        token = part.strip()
        if not token:
            continue
        hour_str, minute_str = token.split(":")
        times.append((int(hour_str), int(minute_str)))
    return times


def run_once():
    load_dotenv()
    graph = build_graph()
    result = graph.invoke({"metrics": {}, "baseline": {}, "off_hours": False})
    print("[ai-service] analysis completed", result.get("result_index"), flush=True)


def parse_misfire_grace_seconds(value: str) -> Optional[int]:
    token = value.strip().lower()
    if token in {"", "none", "always"}:
        return None
    return int(token)


if __name__ == "__main__":
    load_dotenv()
    tz = os.getenv("TZ", "Asia/Seoul")
    run_times = os.getenv("RUN_TIMES", "08:00,18:00")
    run_on_startup = os.getenv("RUN_ON_STARTUP", "false").lower() == "true"
    misfire_grace_seconds = parse_misfire_grace_seconds(
        os.getenv("MISFIRE_GRACE_SECONDS", "3600")
    )

    scheduler = BackgroundScheduler(
        timezone=tz,
        job_defaults={
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": misfire_grace_seconds,
        },
    )
    for hour, minute in parse_run_times(run_times):
        scheduler.add_job(run_once, CronTrigger(hour=hour, minute=minute))

    scheduler.start()

    if run_on_startup:
        run_once()

    print(
        "[ai-service] scheduler started",
        {
            "run_times": run_times,
            "tz": tz,
            "run_on_startup": run_on_startup,
            "misfire_grace_seconds": misfire_grace_seconds,
            "next_runs": [str(job.next_run_time) for job in scheduler.get_jobs()],
        },
        flush=True,
    )
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        scheduler.shutdown()
