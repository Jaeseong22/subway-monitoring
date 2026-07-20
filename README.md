# 서울 지하철 1호선 모니터링

서울 지하철 1호선 실시간 도착정보를 수집하고, ELK 로그와 AI Agent를 활용해 서비스 이상 상태를 탐지하는 관제형 웹 서비스입니다.

사용자는 실시간 도착정보, 역 검색, 즐겨찾기, 개인화 도착 알림을 사용할 수 있고, 관리자는 AI 이상탐지 결과와 운영 지표를 대시보드에서 확인할 수 있습니다.

## 주요 기능

- 서울 지하철 1호선 실시간 도착정보 수집
- 역 검색, 노선도, 역별 도착정보 화면
- 일반 로그인 및 Google OAuth 로그인
- 사용자/관리자 권한 분리
- 사용자별 즐겨찾기 역 관리
- 요일/시간대 기반 개인화 도착 알림
- Spring Boot API, 스케줄러, 외부 API 호출 로그 수집
- Logstash, Elasticsearch, Kibana 기반 ELK 로그 파이프라인
- Golden Signals 기반 운영 지표 수집
  - latency
  - traffic
  - errors
  - saturation
- Python AI Agent 기반 이상탐지
- 관리자 관제 대시보드
- 이상탐지 발표용 데모 데이터 생성 스크립트
- Elasticsearch 스냅샷 백업 스크립트
- Elasticsearch/Kibana 로컬 포트 바인딩 보안 설정

## 전체 구조

```text
서울 열린데이터 API
  -> Spring Boot 수집 스케줄러
     -> MySQL 최신 도착정보 저장
     -> React 사용자 화면 제공
     -> 구조화 로그 생성
        -> Logstash 로그 수집
           -> Elasticsearch 로그 저장
              -> Python AI Agent 이상탐지
                 -> Elasticsearch 이상탐지 결과 저장
                    -> Spring Boot 관리자 API
                       -> React 관리자 대시보드
```

## 기술 스택

| 구분 | 기술 | 역할 |
|---|---|---|
| Frontend | React, TypeScript, Vite, Tailwind CSS, Recharts | 사용자 화면, 즐겨찾기, 개인화 알림, 관리자 대시보드 |
| Backend | Spring Boot, Java, Spring Data JPA | API 서버, 도착정보 수집, 인증, 즐겨찾기, 관리자 API |
| Database | MySQL | 사용자, 세션, 즐겨찾기, 최신 도착정보 저장 |
| Log/Monitoring | Logstash, Elasticsearch, Kibana | 로그 수집, 저장, 검색, 확인 |
| AI Service | Python, LangGraph, OpenAI 연동 가능 구조 | 로그 기반 이상탐지, 판단 근거, 추천 조치사항 생성 |
| Infra | Docker Compose | 전체 서비스 컨테이너 실행 |

## 서비스 주소

Docker Compose로 실행했을 때 기본 주소는 다음과 같습니다.

| 서비스 | 주소 | 설명 |
|---|---|---|
| Frontend | `http://localhost:3000` | React 웹 화면 |
| Backend API | `http://localhost:8080` | Spring Boot API |
| Elasticsearch | `http://localhost:9200` | 로그 저장소, 로컬 접근만 허용 |
| Kibana | `http://localhost:5601` | 로그 검색 화면, 로컬 접근만 허용 |
| MySQL | `localhost:3307` | Docker MySQL 포트 |
| Logstash TCP | `localhost:50000` | 백엔드 JSON 로그 수집 |

## 실행 준비

필요한 도구는 다음과 같습니다.

- Docker Desktop
- Java 25 이상
- Node.js 20 이상
- Python 3.9 이상
- 서울 열린데이터광장 지하철 API 키
- Google OAuth Client ID
- OpenAI API Key

`.env.example`을 복사해서 `.env` 파일을 만든 뒤 값을 채웁니다.

```bash
cp .env.example .env
```

주요 환경 변수는 다음과 같습니다.

```bash
SUBWAY_API_KEY=your_seoul_open_api_key
SUBWAY_API_KEY_SECONDARY=optional_second_key

OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o-mini

GOOGLE_CLIENT_ID=your_google_oauth_web_client_id
VITE_GOOGLE_CLIENT_ID=your_google_oauth_web_client_id

ADMIN_EMAIL=
ADMIN_PASSWORD=
ADMIN_NAME=관리자
```

`GOOGLE_CLIENT_ID`는 백엔드에서 Google ID Token을 검증할 때 사용합니다.

`VITE_GOOGLE_CLIENT_ID`는 프론트엔드 빌드 시 브라우저 로그인 버튼에 사용됩니다.

실제 API 키와 OAuth 값은 `.env`에만 저장하고 GitHub에는 올리지 않습니다.

## Docker Compose 실행

전체 서비스를 한 번에 실행합니다.

```bash
docker compose up -d --build
```

실행 상태를 확인합니다.

```bash
docker compose ps
```

프론트엔드에 접속합니다.

```text
http://localhost:3000
```

Kibana에 접속합니다.

```text
http://localhost:5601
```

전체 서비스를 중지합니다.

```bash
docker compose down
```

## 수평 확장 (API 서버 여러 대 실행)

기본 구성은 `backend` 한 대가 API와 수집 스케줄러를 모두 담당합니다. 확장 오버레이를 겹치면 역할이 분리되어 API 계층을 여러 대로 늘릴 수 있습니다.

```bash
docker compose -f docker-compose.yml -f docker-compose.scale.yml up -d --build --scale backend=2
```

| 서비스 | 역할 | 대수 |
|---|---|---|
| `lb` | nginx 로드밸런서, `8080` 노출 | 1 |
| `backend` | API 전용 (`APP_SCHEDULER_ENABLED=false`) | N |
| `collector` | 수집 전용 (`APP_SCHEDULER_ENABLED=true`) | **반드시 1** |

분산 동작 확인:

```bash
curl localhost:8080/actuator/health/readiness
docker compose -f docker-compose.yml -f docker-compose.scale.yml logs lb | grep upstream=
```

### 수집기를 반드시 1대로 유지해야 하는 이유

수집 스케줄러가 여러 인스턴스에서 동시에 돌면 다음 문제가 발생합니다.

- 서울 열린데이터 API를 인스턴스 수만큼 중복 호출해 **일일 쿼터를 소진**합니다.
- `arrival_info`는 전체 삭제 후 재삽입하는 구조이므로 인스턴스끼리 **서로가 방금 쓴 데이터를 지웁니다**. 그 사이 사용자는 빈 결과를 받습니다.
- `SchedulerPolicy`의 실행 카운터와 `SeoulSubwayClient`의 사이클 카운터는 **인스턴스 로컬 상태**라 "2턴 중 1회" 주기 정책이 깨집니다.

따라서 API 인스턴스는 스케줄러를 끄고, 수집 전용 프로세스 하나만 켭니다. 여러 수집기를 띄우려면 ShedLock 같은 분산 락이 별도로 필요합니다.

### 인스턴스 수 인식

각 인스턴스는 Golden Signals 로그에 자신의 `instance_id`(컨테이너 호스트명, 또는 `INSTANCE_ID` 환경변수)를 남깁니다. AI 이상탐지는 분석 창 안에서 **서로 다른 `instance_id` 개수**를 세어 실제 가동 인스턴스 수를 판단합니다.

`requests_per_second`는 **인스턴스당** 값입니다. 클러스터 합계로 바꾸면 인스턴스를 늘린 직후 기준선(과거 인스턴스당 값) 대비 배수가 튀어 **확장 자체가 트래픽 급증으로 오탐**됩니다.

### 헬스체크

`spring-boot-starter-actuator`로 다음 엔드포인트를 제공합니다.

| 엔드포인트 | 용도 |
|---|---|
| `/actuator/health/readiness` | 트래픽을 받아도 되는 상태인지 (LB 편입 판단) |
| `/actuator/health/liveness` | 프로세스가 살아있는지 (재시작 판단) |

Compose의 `healthcheck`와 `depends_on: condition: service_healthy`로 기동 순서를 보장합니다.

## 로컬 개발 실행

백엔드만 로컬로 실행합니다.

```bash
cd backend
./gradlew bootRun
```

프론트엔드만 로컬로 실행합니다.

```bash
cd frontend
npm install
npm run dev
```

AI 서비스를 로컬로 실행합니다.

```bash
cd ai_service
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## 데이터 저장 구조

MySQL은 서비스에 필요한 현재 상태 데이터를 저장합니다.

- 사용자 계정
- 로그인 세션
- 지하철 역 정보
- 사용자 즐겨찾기 역
- 최신 도착정보

현재 `arrival_info`는 과거 이력을 저장하지 않고 최신 도착정보 스냅샷만 유지합니다. 스케줄러가 새 도착정보를 수집하면 기존 도착정보를 삭제하고 최신 데이터를 다시 저장합니다.

Elasticsearch는 시간 흐름에 따른 로그와 분석 결과를 저장합니다.

- `subway-logs-*`
  - API 호출 로그
  - 스케줄러 실행 로그
  - 트래픽 로그
  - Golden Signals 요약 로그
  - 사용자 역 조회 행동 로그
- `subway-anomaly-results`
  - AI 이상탐지 결과
  - 판단 근거
  - 추천 조치사항
  - 관련 메트릭 추이

## Golden Signals 수집

백엔드는 API 요청과 시스템 상태를 집계하여 1분마다 Golden Signals 요약 로그를 남깁니다.

| 지표 | 의미 | 수집 필드 |
|---|---|---|
| Latency | 요청 처리 지연 | `elapsed_ms`, `avg_elapsed_ms`, `duration_ms` |
| Traffic | 서비스 요청량 | `request_count`, `requests_per_second`, `endpoint` |
| Errors | 실패율과 오류 | `success`, `error_count`, `error_rate`, `error_msg` |
| Saturation | 시스템 포화도 | `cpu_percent`, `memory_percent`, `queue_depth`, `in_flight_requests`, `max_concurrent_requests` |

예시 로그:

```text
event_type=TRAFFIC
event_name=golden_signals_summary
request_count=120
requests_per_second=2.00
error_count=3
error_rate=0.0250
avg_elapsed_ms=42.5
cpu_percent=35.2
memory_percent=61.8
queue_depth=5
```

AI Agent는 이 로그를 활용해 트래픽 급증, 오류율 증가, 서버 자원 포화 가능성을 판단합니다.

## AI 이상탐지

AI 서비스는 Elasticsearch의 `subway-logs-*` 인덱스에서 최근 로그를 조회하고 서비스 상태를 분석합니다.

기본 분석 대상:

- 외부 서울 지하철 API 호출 수
- API 실패 수
- API 오류율
- 평균/최대 응답 시간
- 백엔드 요청량
- 초당 요청 수
- CPU 사용률
- 메모리 사용률
- 큐 깊이
- 동시 요청 수
- 스케줄러 실행/실패 로그
- 수집 메트릭

### 판단 방식: 과거 기준선(baseline) 대비 통계 비교

이상탐지는 고정 임계값만 쓰지 않고, **과거 같은 시간대(hour_of_day) + 평일/주말(is_weekend)의 최근 28일 로그로 신호별 기준선(평균±표준편차)을 만들고, 현재 값을 baseline과 비교**합니다. Google SRE의 네 가지 golden signals(latency/traffic/errors/saturation)를 실제 로그 필드에 매핑해 신호별로 평가합니다.

| 신호 | 판단 근거 | 기준 |
|---|---|---|
| Errors (API 오류율) | 절대 기준 | 5% 이상 주의 / 20% 이상 위험 |
| Latency (응답시간) | baseline 배수 **AND** z-score | 기준선 대비 1.5배 주의 / 2.0배 위험 (z 게이트 동시 충족 필요) |
| Traffic (요청량) | baseline 대비 급증 **AND** z-score | 기준선 대비 2배 이상 급증, 없으면 req/s 절대 가드레일 |
| Saturation (CPU/메모리) | 절대 사용률 | 60% 이상 주의 / 80% 이상 위험 |
| Scheduler (수집 실패) | 절대 | 실패 1건 이상 위험 |
| Collection (수집량 급감) | baseline 대비 | 기준선의 50% 이하로 감소 시 주의 |

#### 비교 규칙: 평균은 평균끼리, 피크는 피크끼리

시계열 이상탐지에서 가장 흔한 오류는 **분석 창의 최댓값을 기준선의 평균과 비교**하는 것이다. `E[max of N] > mean`이므로 정상 상태에서도 배수 임계를 상시 초과해 구조적 거짓양성이 발생한다. 따라서 두 축으로 나누어 판단한다.

- **(a) 창 평균 vs 기준선 평균** — 배수 조건과 z-score 조건을 **모두** 만족해야 이상으로 본다.
  - `z = (현재값 − 기준선평균) / 기준선표준편차`, 기본 게이트 `z ≥ 2` (위험은 `z ≥ 3`)
- **(b) 창 피크 vs 기준선 p99** — 꼬리 대 꼬리(tail-vs-tail) 비교. 피크가 기준선 상위 1%를 넘으면 위험으로 승격한다.

#### 그 외 판정 규칙

- 절대 가드레일은 창 길이에 의존하는 **총 요청수가 아니라 req/s**로 판단한다(기본 20 주의 / 50 위험). 총 요청수 기준은 창 길이에 따라 의미가 달라져 상시 발화하는 상수 알람이 된다.
- 기준선 표본이 부족하면(기본 5건 미만) 절대 임계값 가드레일로 안전하게 판단한다.
- 기준선 시간 버킷은 **분석 창의 중앙 시각** 기준으로 고른다(실행 시각 기준으로 고르면 러시아워 경계에서 체계적 편향이 생긴다).
- 운영 종료 시간대(off-hours)에는 수집이 멈추므로 트래픽/포화만 평가한다.
- **플래핑 방지**: 연속 `ANOMALY_CONSECUTIVE_N`회(기본 2회) 감지된 신호만 확정 알람으로 승격한다. 미확정 신호는 `pending_signals`로 기록된다. 이력은 별도 저장소 없이 `subway-anomaly-results`의 직전 결과를 재사용한다.
- 임계값·z-score 기준은 환경변수로 조정할 수 있다(`Z_SCORE_WARN`, `LATENCY_WARN_RATIO`, `TRAFFIC_RPS_CRIT`, `CPU_CRIT` 등).

#### 실행 주기

기본은 **5분 간격 상시 관측**(`RUN_INTERVAL_MINUTES=5`)이다. `RUN_TIMES`를 지정하면 고정 시각 모드로 동작하지만, 그 시각 외에는 관측 공백이 생기므로 운영 목적에는 권장하지 않는다.

#### LLM의 역할과 한계

`ANALYSIS_MODE=llm`이어도 **판정과 수치는 LLM이 바꿀 수 없다.** LLM 응답은 `graph/llm_merge.py`에서 병합되며, 채택되는 것은 제목·요약·근거·조치사항 등 **서술 텍스트뿐**이다. `overall_status`, `severity`, 이상 건수, `metric_trend` 수치는 통계 결과가 강제된다. 프롬프트로 "통계 결과를 따르라"고 지시하는 것만으로는 모델이 판정을 뒤집는 것을 막을 수 없기 때문이다.

판단 로직은 서드파티 의존성이 없는 `ai_service/graph/detection.py`, LLM 출력 검증은 `ai_service/graph/llm_merge.py`에 분리되어 있고 `ai_service/tests/test_detection.py`로 단위 테스트한다.

```bash
cd ai_service && python3 tests/test_detection.py
```

근거 자료: [Google SRE — The Four Golden Signals](https://sre.google/sre-book/monitoring-distributed-systems/), [Grafana — The RED Method](https://grafana.com/blog/the-red-method-how-to-instrument-your-services/), [Brendan Gregg — The USE Method](https://www.brendangregg.com/usemethod.html).

분석 결과는 `subway-anomaly-results` 인덱스에 저장되고 관리자 대시보드에 표시됩니다.

## 자동 대응 (auto-remediation)

탐지에서 끝나지 않고 **감지 → 제안 → 승인 → 실행 → 검증 → 롤백**의 닫힌 루프를 구성합니다.

```text
이상탐지 (ai_service)
  → 조치 제안 저장 (subway-remediation-actions, status=PENDING)
    → 관리자 승인 (POST /api/v1/admin/remediation/{id}/approve → APPROVED)
      → 워커가 docker compose --scale 실행 (EXECUTED)
        → N분 후 지표 재확인 (SUCCEEDED | FAILED)
          → 실패 시 롤백 조치 자동 생성
```

### 권한 분리

| 주체 | 권한 |
|---|---|
| `ai_service` | 제안만 생성. 인프라를 조작하지 않음 |
| 백엔드 API | 상태 전이(승인/거부)만. 인프라를 조작하지 않음 |
| `remediation_worker.py` | **호스트에서 실행**. 실제 확장/축소를 수행 |

워커를 컨테이너에 넣으려면 Docker 소켓을 마운트해야 하는데, 이는 사실상 호스트 root 권한을 주는 것과 같습니다. 그래서 실행 권한은 호스트의 워커에만 두었습니다.

### 워커 실행

기본은 **dry-run**입니다. 실제로 확장하려면 명시적으로 켜야 합니다.

```bash
# 계획만 출력 (기본)
python ai_service/remediation_worker.py

# 실제 실행
REMEDIATION_EXECUTE=true python ai_service/remediation_worker.py
```

### 가드레일

오탐 한 번이 무한 확장으로 이어지지 않도록 다음을 강제합니다.

| 가드레일 | 기본값 | 이유 |
|---|---|---|
| `REMEDIATION_MAX_REPLICAS` | 4 | 상한 도달 시 자동 조치 대신 사람이 봐야 한다고 기록 |
| `REMEDIATION_COOLDOWN_MINUTES` | 15 | 확장 직후엔 지표가 안정될 시간이 필요 |
| 열린 조치 중복 방지 | — | 처리 안 된 제안이 있으면 새로 만들지 않음 |
| `REMEDIATION_EXPIRE_AFTER_MINUTES` | 60 | 승인 안 된 오래된 제안의 뒤늦은 실행 차단 |
| `REMEDIATION_AUTO_APPROVE` | false | 기본은 human-in-the-loop |

**확장으로 해결되는 신호만 대상입니다** — `traffic` / `saturation` / `latency`. 스케줄러 실패나 외부 API 장애는 서버를 늘려도 해결되지 않으므로 조치를 제안하지 않습니다.

### 검증과 롤백

조치를 하고 끝내면 "고쳤다고 믿는 것"이지 고친 게 아닙니다. 실행 후 `REMEDIATION_VERIFY_AFTER_MINUTES`(기본 10분)가 지나면 지표를 다시 보고, **촉발 신호가 사라졌는지**로 성패를 판정합니다. 남아 있으면 역방향 조치(롤백)를 자동 생성합니다. 롤백의 롤백은 만들지 않아 무한 왕복을 막습니다.

### 관리자 API

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/api/v1/admin/remediation` | 조치 목록 (최신순) |
| POST | `/api/v1/admin/remediation/{id}/approve` | 승인 |
| POST | `/api/v1/admin/remediation/{id}/reject` | 거부 |

이미 처리된 조치를 다시 승인하면 `409 Conflict`를 반환합니다(뒤늦은 승인으로 인한 의도치 않은 확장 방지).

로직은 의존성 없는 `ai_service/graph/remediation.py`에 분리되어 있고 `ai_service/tests/test_remediation.py`로 단위 테스트합니다.

```bash
cd ai_service && python3 tests/test_remediation.py
```

## CI/CD

`.github/workflows/ci.yml` — push/PR마다 실행합니다.

| 잡 | 내용 |
|---|---|
| `backend` | MySQL 서비스 컨테이너를 띄우고 `./gradlew build` (테스트 포함) |
| `ai-service` | detection/remediation 단위 테스트 + 의존성 포함 import 검증 |
| `frontend` | `npm ci` → lint(리포트만) → `tsc --noEmit` + vite build |
| `images` | backend/frontend/ai-service 이미지 빌드 검증 |
| `compose` | compose 문법 + **확장 토폴로지 불변식 검증** |

토폴로지 검증(`scripts/assert_scaled_topology.py`)은 다음이 깨지면 CI를 실패시킵니다.

- `backend`에서 스케줄러가 켜지는 것 (외부 API 중복 호출 + 도착정보 삭제 경합)
- `backend`에 `container_name`이나 host 포트가 고정되는 것 (`--scale` 불가)

`.github/workflows/release.yml` — `v*` 태그를 밀면 이미지를 GHCR에 푸시합니다. 실제 서버 배포 잡은 배포 대상이 정해진 뒤 추가하는 것이 맞습니다(대상 없는 배포 단계는 항상 실패하는 잡이 됩니다).

`backend/Dockerfile`의 `-x test`는 의도적으로 유지했습니다 — 테스트는 CI에서 DB를 붙여 실행하고, 이미지 빌드는 산출물 생성에만 집중하는 것이 표준적인 분리입니다.

### 컨테이너 이미지

공개 이미지이므로 로그인 없이 받을 수 있습니다.

```bash
docker pull ghcr.io/jaeseong22/subway-monitoring/backend:0.2.0
docker pull ghcr.io/jaeseong22/subway-monitoring/frontend:0.2.0
docker pull ghcr.io/jaeseong22/subway-monitoring/ai-service:0.2.0
```

태그는 `0.2.0`(정확한 버전), `0.2`(마이너), `latest`, `sha-<커밋>` 형태로 제공됩니다.

> **`linux/amd64` 전용입니다.** GitHub Actions 러너가 amd64이고 멀티플랫폼 빌드는 QEMU 에뮬레이션이라 릴리스가 크게 느려져서, 배포 대상(리눅스 서버)에 맞춰 amd64만 발행합니다.
>
> Apple Silicon Mac에서는 그냥 `docker pull`이 `no matching manifest for linux/arm64` 로 실패하므로 플랫폼을 명시해야 합니다. Rosetta 에뮬레이션으로 동작하며 네이티브보다 느립니다.
>
> ```bash
> docker pull --platform linux/amd64 ghcr.io/jaeseong22/subway-monitoring/backend:0.2.0
> ```
>
> Mac에서 로컬 개발할 때는 이미지를 받지 말고 `docker compose up -d --build`로 직접 빌드하는 편이 빠릅니다(네이티브 arm64로 빌드됩니다).

## 이상탐지 데모

발표나 검증을 위해 합성 로그와 이상탐지 결과를 생성할 수 있습니다.

```bash
scripts/run_anomaly_demo.sh normal
scripts/run_anomaly_demo.sh api-failure
scripts/run_anomaly_demo.sh traffic-spike
scripts/run_anomaly_demo.sh scheduler-failure
scripts/run_anomaly_demo.sh restore
```

시나리오 설명:

- `normal`: 정상 상태 로그를 생성합니다.
- `api-failure`: 외부 API timeout/429 오류 상황을 생성합니다.
- `traffic-spike`: 요청량, CPU, 메모리, 큐 증가 상황을 생성합니다.
- `scheduler-failure`: 수집 스케줄러 실패 상황을 생성합니다.
- `restore`: 데모 로그가 아니라 실제 라이브 로그 분석 상태로 되돌립니다.

발표 후에는 반드시 다음 명령으로 라이브 분석 상태로 복구합니다.

```bash
scripts/run_anomaly_demo.sh restore
```

## 즐겨찾기 알림 데모

즐겨찾기 알림은 다음 조건을 만족할 때 표시됩니다.

- 로그인한 사용자의 즐겨찾기 역
- 최근 30일 동안 같은 요일과 같은 시간대에 3회 이상 조회
- 해당 역에 15분 이내 도착 예정 열차가 있음

검증 데이터를 생성합니다.

```bash
scripts/run_favorite_alert_demo.sh create
```

발표 중 현재 요일/시간대에 계속 맞춰 유지합니다.

```bash
scripts/run_favorite_alert_demo.sh watch
```

검증 데이터를 정리합니다.

```bash
scripts/run_favorite_alert_demo.sh cleanup
```

## Elasticsearch 백업

Elasticsearch 로그와 이상탐지 결과를 스냅샷으로 백업할 수 있습니다.

```bash
scripts/elk_snapshot.sh
```

백업 대상:

- `subway-logs-*`
- `subway-anomaly-results`

## 보안 주의사항

`docker-compose.yml`에서 Elasticsearch와 Kibana는 `127.0.0.1`에만 바인딩되어 있습니다.

```text
127.0.0.1:9200
127.0.0.1:5601
```

이 설정은 로컬 개발 환경에서 외부 접근을 막기 위한 것입니다. Elasticsearch `9200` 포트와 Kibana `5601` 포트를 공개 인터넷에 직접 노출하지 마세요.

운영 환경에 배포하려면 다음 설정이 필요합니다.

- Elasticsearch/Kibana 인증
- TLS 적용
- 네트워크 접근 제어
- 관리자 계정 보호
- API Rate Limit
- 실제 운영용 로그 보존 정책

## 프로젝트 구조

```text
backend/        Spring Boot API, 수집 스케줄러, 인증, 로그 수집
frontend/       React 사용자 화면 및 관리자 대시보드
ai_service/     Python AI 이상탐지 서비스
logstash/       Logstash 파이프라인 설정
scripts/        데모 데이터, AI 실행, ELK 백업 스크립트
docs/           발표 자료와 설계 문서
docker-compose.yml
```

## 참고 자료

- 서울 열린데이터광장, 서울시 지하철 실시간 도착정보
  - https://data.seoul.go.kr/dataList/OA-12764/F/1/datasetView.do

- Google for Developers, GTFS Realtime Overview
  - https://developers.google.com/transit/gtfs-realtime

- Google SRE Book, Monitoring Distributed Systems
  - https://sre.google/sre-book/monitoring-distributed-systems/

- Elastic, Observability
  - https://www.elastic.co/observability

- Elastic Docs, Anomaly detection with machine learning
  - https://www.elastic.co/docs/explore-analyze/machine-learning/anomaly-detection

- IBM, What is AIOps?
  - https://www.ibm.com/think/topics/aiops

- Uber, Real-time Data Infrastructure at Uber
  - https://arxiv.org/abs/2104.00087

- A Survey of AIOps for Failure Management in the Era of Large Language Models
  - https://arxiv.org/abs/2406.11213
