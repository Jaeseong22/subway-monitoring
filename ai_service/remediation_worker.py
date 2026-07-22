"""자동 대응 실행 워커 — 승인된 조치를 실행하고, 결과를 검증하고, 실패하면 롤백한다.

이 워커는 **호스트에서 실행한다.** 컨테이너 안에서 돌리려면 Docker 소켓을 마운트해야
하는데, 그것은 사실상 호스트 root 권한을 주는 것과 같다. 분석 프로세스(ai_service)는
제안만 하고, 인프라를 실제로 바꾸는 권한은 이 워커에만 둔다.

기본은 **dry-run**이다. `REMEDIATION_EXECUTE=true`를 명시해야 실제로 명령을 실행한다.

실행:
    cd <repo-root>
    REMEDIATION_EXECUTE=false python ai_service/remediation_worker.py        # 계획만 출력
    REMEDIATION_EXECUTE=true  python ai_service/remediation_worker.py        # 실제 확장/축소

루프:
    APPROVED  → 명령 실행 → EXECUTED
    EXECUTED  → 검증 대기 시간 경과 후 최신 분석 결과로 판정 → SUCCEEDED | FAILED(+롤백 생성)
    PENDING   → 만료 시간 경과 시 EXPIRED
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 서드파티 의존성(dotenv/elasticsearch)은 main()에서만 필요하다. 모듈 레벨에 두면
# process_once 같은 순수 로직을 테스트할 때도 의존성 설치를 강제하게 되므로,
# main()에서 지연 import한다. remediation은 의존성이 없어 여기서 import해도 된다.
from graph import remediation  # noqa: E402

LOGGER = logging.getLogger("remediation-worker")

# compose 파일은 저장소 루트 기준이다. cwd에 의존하면 어느 디렉터리에서 실행했는지에 따라
# "no such file or directory"로 실패한다.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _compose_files() -> list[str]:
    raw = os.getenv("REMEDIATION_COMPOSE_FILES", "docker-compose.yml,docker-compose.scale.yml")
    files = []
    for part in raw.split(","):
        name = part.strip()
        if not name:
            continue
        files.append(name if os.path.isabs(name) else os.path.join(REPO_ROOT, name))
    return files


def execute(action: dict, dry_run: bool) -> tuple[bool, str]:
    """조치 명령을 실행한다. (성공여부, 메모)를 반환한다."""
    cmd = remediation.scale_command(action, _compose_files())
    printable = " ".join(cmd)
    if dry_run:
        LOGGER.info("[DRY-RUN] 실행하지 않고 계획만 출력합니다: %s", printable)
        return True, f"dry-run: {printable}"

    LOGGER.info("실행: %s", printable)
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                                   check=False, cwd=REPO_ROOT)
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"실행 실패: {exc}"

    if completed.returncode != 0:
        tail = (completed.stderr or completed.stdout or "").strip()[-500:]
        return False, f"명령이 코드 {completed.returncode}로 실패: {tail}"
    return True, f"실행 완료: {printable}"


def latest_result(client: "ElasticsearchClient") -> dict:
    """검증·재계획에 사용할 가장 최근 분석 결과(result/metrics/diagnosis)."""
    return client.fetch_latest_analysis()


def process_once(client: "ElasticsearchClient", cfg: dict, dry_run: bool) -> int:
    """열려 있는 조치들을 한 번 훑는다. 처리한 건수를 반환한다."""
    handled = 0
    for action in client.fetch_recent_actions(size=50):
        action_id = action.get("action_id")
        status = action.get("status")

        if status == remediation.PENDING:
            if remediation.expire_stale(action, cfg=cfg):
                client.update_action(action_id, remediation.with_status(
                    action, remediation.EXPIRED,
                    f"{cfg['expire_after_minutes']}분 동안 승인되지 않아 만료했습니다."))
                LOGGER.info("만료 id=%s", action_id)
                handled += 1
            continue

        if status == remediation.APPROVED:
            running = remediation.with_status(action, remediation.EXECUTING, "실행을 시작합니다.")
            client.update_action(action_id, running)
            ok, note = execute(action, dry_run)
            if ok:
                client.update_action(action_id, remediation.with_status(
                    running, remediation.EXECUTED, note,
                    executed_at=remediation.now_iso(), dry_run=dry_run))
            else:
                client.update_action(action_id, remediation.with_status(
                    running, remediation.FAILED, note))
                LOGGER.error("실행 실패 id=%s %s", action_id, note)
            handled += 1
            continue

        if status == remediation.EXECUTING:
            # 워커가 실행 중 죽으면 이 조치가 EXECUTING에 영원히 남아 이후 모든 제안을
            # 차단한다. 타임아웃을 넘으면 정리한다.
            reaped = remediation.reap_stuck(action, cfg=cfg)
            if reaped:
                new_status, note = reaped
                client.update_action(action_id, remediation.with_status(action, new_status, note))
                LOGGER.warning("멈춘 조치 정리 id=%s → %s (%s)", action_id, new_status, note)
                handled += 1
            continue

        if status == remediation.EXECUTED:
            # 검증 전에 워커가 죽어 오래 방치된 EXECUTED도 정리한다.
            reaped = remediation.reap_stuck(action, cfg=cfg)
            if reaped:
                new_status, note = reaped
                client.update_action(action_id, remediation.with_status(action, new_status, note))
                LOGGER.warning("멈춘 조치 정리 id=%s → %s (%s)", action_id, new_status, note)
                handled += 1
                continue
            if not remediation.is_ready_to_verify(action, cfg=cfg):
                continue
            latest = latest_result(client)
            verdict = remediation.verify(action, latest["result"])
            client.update_action(action_id, remediation.with_status(
                action, verdict["status"], verdict["note"]))
            LOGGER.info("검증 id=%s → %s (%s)", action_id, verdict["status"], verdict["note"])
            if verdict["rollback"] and not action.get("is_rollback"):
                # 재계획: 단순 롤백 대신 진단 결과를 근거로 추가 확장 vs 롤백을 결정한다.
                # 롤백 조치 자신은 재계획하지 않는다(무한 왕복 방지).
                plan = remediation.replan(action, latest["result"], latest["metrics"],
                                          latest["diagnosis"], cfg=cfg)
                next_id = client.save_action(plan["next"])
                LOGGER.warning("재계획 id=%s decision=%s → 새 조치 %s (원본 %s)",
                               action_id, plan["decision"], next_id, action_id)
            handled += 1

    return handled


def main() -> None:
    from dotenv import load_dotenv
    from es_client import ElasticsearchClient

    load_dotenv()
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    cfg = remediation.config()
    dry_run = os.getenv("REMEDIATION_EXECUTE", "false").strip().lower() != "true"
    interval = int(os.getenv("REMEDIATION_POLL_SECONDS", "30"))

    LOGGER.info(
        "자동 대응 워커 시작 %s",
        {"dry_run": dry_run, "poll_seconds": interval, "service": cfg["service"],
         "replicas": f"{cfg['min_replicas']}~{cfg['max_replicas']}",
         "auto_approve": cfg["auto_approve"], "compose_files": _compose_files()},
    )
    if dry_run:
        LOGGER.warning("dry-run 모드입니다. 실제로 확장/축소하려면 REMEDIATION_EXECUTE=true 로 실행하세요.")

    client = ElasticsearchClient()
    while True:
        try:
            process_once(client, cfg, dry_run)
        except KeyboardInterrupt:
            raise
        except Exception:
            LOGGER.exception("조치 처리 중 오류 — 다음 주기에 다시 시도합니다.")
        time.sleep(interval)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        LOGGER.info("워커를 종료합니다.")
