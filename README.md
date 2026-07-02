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
| Errors (API 오류율) | 절대 기준 + baseline 대비 | 5% 이상 주의 / 20% 이상 위험 |
| Latency (응답시간) | baseline 배수 (z-score) | 기준선 대비 1.5배 주의 / 2.0배 위험 |
| Traffic (요청량) | baseline 대비 급증 (z-score) | 기준선 대비 2배 이상 급증, 절대 요청량 가드레일 병행 |
| Saturation (CPU/메모리) | 절대 사용률 | 60% 이상 주의 / 80% 이상 위험 |
| Scheduler (수집 실패) | 절대 | 실패 1건 이상 위험 |
| Collection (수집량 급감) | baseline 대비 | 기준선의 50% 이하로 감소 시 주의 |

- 통계 비교의 핵심 공식: `z = (현재값 − 기준선평균) / 기준선표준편차`, `|z| > 2`면 이상으로 본다.
- 기준선 표본이 부족하면(기본 5건 미만) 절대 임계값 가드레일로 안전하게 판단한다.
- 운영 종료 시간대(off-hours)에는 수집이 멈추므로 트래픽/포화만 평가한다.
- 임계값·z-score 기준은 환경변수로 조정할 수 있다(`Z_SCORE_WARN`, `LATENCY_WARN_RATIO`, `CPU_CRIT` 등).

판단 로직은 서드파티 의존성이 없는 `ai_service/graph/detection.py`에 분리되어 있고 `ai_service/tests/test_detection.py`로 단위 테스트한다.

근거 자료: [Google SRE — The Four Golden Signals](https://sre.google/sre-book/monitoring-distributed-systems/), [Grafana — The RED Method](https://grafana.com/blog/the-red-method-how-to-instrument-your-services/), [Brendan Gregg — The USE Method](https://www.brendangregg.com/usemethod.html).

분석 결과는 `subway-anomaly-results` 인덱스에 저장되고 관리자 대시보드에 표시됩니다.

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
