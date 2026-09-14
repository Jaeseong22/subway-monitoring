import logging
import os
import time
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from dotenv import load_dotenv

from graph.agent import build_graph

LOGGER = logging.getLogger("ai-service")


def parse_run_times(value: str) -> list[tuple[int, int]]:
    times = []
    for part in value.split(","):
        token = part.strip()
        if not token:
            continue
        hour_str, minute_str = token.split(":")
        times.append((int(hour_str), int(minute_str)))
    return times


def apply_schedule_mode_defaults() -> None:
    """고정 시각 모드(RUN_TIMES)에서는 연속 N회 디바운스를 끈다.

    디바운스는 "직전 실행"과 비교하는데, 하루 2회 모드에서 직전 실행은 10시간 전이다.
    연속 2회 조건을 그대로 두면 아침·저녁 모두 이상이어야 확정되어 10분짜리 급증은
    영원히 확정되지 않는다. 고정 시각 모드에서는 검증 패널이 오탐을 거른다.
    """
    if os.getenv("RUN_TIMES", "").strip() and os.getenv("ANOMALY_CONSECUTIVE_N", "2") != "1":
        LOGGER.info("고정 시각 모드: 연속 감지 조건(ANOMALY_CONSECUTIVE_N)을 1로 둡니다.")
        os.environ["ANOMALY_CONSECUTIVE_N"] = "1"


def run_once():
    load_dotenv()
    apply_schedule_mode_defaults()
    graph = build_graph()
    try:
        result = graph.invoke({"metrics": {}, "baseline": {}, "off_hours": False})
    except Exception:
        # 스케줄 실행이 예외로 죽으면 이후 주기가 조용히 멈출 수 있으므로 삼키되 기록한다.
        LOGGER.exception("분석 실행 실패")
        return
    verdict = result.get("result", {}) or {}
    LOGGER.info(
        "분석 완료 index=%s status=%s anomalies=%s detected=%s",
        result.get("result_index"),
        verdict.get("overall_status"),
        verdict.get("today_anomaly_count"),
        verdict.get("detected_keys"),
    )


def parse_misfire_grace_seconds(value: str) -> Optional[int]:
    token = value.strip().lower()
    if token in {"", "none", "always"}:
        return None
    return int(token)


if __name__ == "__main__":
    load_dotenv()
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    tz = os.getenv("TZ", "Asia/Seoul")
    # 기본은 상시 관측(5분 간격). 하루 몇 번만 도는 고정 시각 모드는 관측 공백이
    # 커서(24시간 중 1시간만 관측) 실제 장애를 놓친다. RUN_TIMES를 명시했을 때만
    # 기존 고정 시각 모드로 동작한다.
    run_times = os.getenv("RUN_TIMES", "").strip()
    interval_minutes = int(os.getenv("RUN_INTERVAL_MINUTES", "5"))
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
    if run_times:
        mode = f"cron({run_times})"
        for hour, minute in parse_run_times(run_times):
            scheduler.add_job(run_once, CronTrigger(hour=hour, minute=minute))
    else:
        mode = f"interval({interval_minutes}m)"
        scheduler.add_job(run_once, IntervalTrigger(minutes=interval_minutes))

    scheduler.start()

    if run_on_startup:
        run_once()

    LOGGER.info(
        "스케줄러 시작 %s",
        {
            "mode": mode,
            "tz": tz,
            "run_on_startup": run_on_startup,
            "misfire_grace_seconds": misfire_grace_seconds,
            "next_runs": [str(job.next_run_time) for job in scheduler.get_jobs()],
        },
    )
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        scheduler.shutdown()
