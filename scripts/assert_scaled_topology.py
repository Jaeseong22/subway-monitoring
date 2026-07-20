#!/usr/bin/env python3
"""확장 구성(docker-compose.scale.yml)이 안전한 형태인지 검증한다.

CI에서 `docker compose config` 결과를 받아 확인한다. 아래 불변식이 깨지면
수평 확장 시 실제 장애가 난다:

- backend(API)에서 스케줄러가 켜지면 → 외부 API를 인스턴스 수만큼 중복 호출하고
  arrival_info를 서로 지운다.
- backend에 container_name이나 host 포트가 고정되면 → `--scale`이 아예 동작하지 않는다.

사용법:
    docker compose -f docker-compose.yml -f docker-compose.scale.yml config > /tmp/scaled.yml
    python3 scripts/assert_scaled_topology.py /tmp/scaled.yml
"""
import sys

import yaml


def scheduler_flag(service: dict) -> str:
    env = service.get("environment") or {}
    if isinstance(env, list):
        # `KEY=VALUE` 리스트 형태로 나올 수도 있다.
        env = dict(item.split("=", 1) for item in env if "=" in item)
    return str(env.get("APP_SCHEDULER_ENABLED", "")).strip().lower()


def main(path: str) -> int:
    with open(path, encoding="utf-8") as handle:
        services = (yaml.safe_load(handle) or {}).get("services", {})

    failures = []

    for name in ("backend", "collector", "lb"):
        if name not in services:
            failures.append("서비스 '%s'가 확장 구성에 없습니다." % name)
    if failures:
        for message in failures:
            print("FAIL:", message)
        return 1

    backend, collector = services["backend"], services["collector"]

    backend_flag = scheduler_flag(backend)
    if backend_flag != "false":
        failures.append(
            "backend는 스케줄러가 꺼져 있어야 합니다 (APP_SCHEDULER_ENABLED=false, 현재 %r)." % backend_flag)

    collector_flag = scheduler_flag(collector)
    if collector_flag != "true":
        failures.append(
            "collector는 스케줄러가 켜져 있어야 합니다 (APP_SCHEDULER_ENABLED=true, 현재 %r)." % collector_flag)

    if backend.get("container_name"):
        failures.append(
            "backend에 container_name이 고정되어 있으면 --scale로 여러 대를 띄울 수 없습니다.")

    if backend.get("ports"):
        failures.append(
            "backend가 host 포트를 직접 바인딩하면 --scale 시 포트 충돌이 납니다. LB를 통해 노출하세요.")

    if not services["lb"].get("ports"):
        failures.append("lb가 host 포트를 노출하지 않아 외부에서 접근할 수 없습니다.")

    for message in failures:
        print("FAIL:", message)
    if failures:
        return 1

    print("scaled topology ok: backend=API only, collector=scheduler, lb exposed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "/dev/stdin"))
