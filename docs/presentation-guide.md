# 서울 지하철 1호선 모니터링 프로젝트 발표 자료

## 1. 프로젝트 개요

이 프로젝트는 서울 지하철 1호선의 실시간 도착 정보를 수집하고, 서비스 상태를 ELK 로그 기반으로 분석하며, AI 이상탐지 결과를 관리자 대시보드에 제공하는 관제 시스템이다.

또한 사용자의 역 조회 행동을 로그로 수집해, 사용자가 자주 확인하는 요일과 시간대에 즐겨찾기 역 도착 알림을 제공하는 개인화 기능도 포함한다.

전체 데이터 흐름은 다음과 같다.

```text
서울 열린데이터 API
-> Spring Boot 백엔드 스케줄러
-> MySQL에 최신 도착정보 저장
-> 백엔드 실행 로그를 Logstash로 전송
-> Elasticsearch에 로그 저장
-> AI 서비스가 최근 로그 분석
-> 이상탐지 결과를 Elasticsearch에 저장
-> React 대시보드에서 결과 표시
```

## 2. 주요 기술 스택

| 영역 | 기술 |
|---|---|
| Frontend | React, TypeScript, Vite, Tailwind CSS |
| Backend | Spring Boot, Java, JPA |
| Database | MySQL |
| Log/Monitoring | Logstash, Elasticsearch, Kibana |
| AI Service | Python, LangGraph, OpenAI 연동 가능 |
| Runtime | Docker Compose |

## 3. 실시간 도착정보 수집 로직

백엔드의 `ArrivalUpdateScheduler`가 서울 열린데이터 API에서 실시간 지하철 도착 정보를 수집한다.

수집 대상은 서울 지하철 1호선이다.

수집된 데이터는 MySQL의 `arrival_info` 테이블에 저장된다.

현재 구조에서는 과거 전체 기록을 저장하지 않고, 최신 도착 상태만 유지한다.

즉, 매 수집 시점마다 기존 도착정보를 삭제하고 최신 데이터를 다시 저장한다.

```text
arrival_info = 현재 시점의 최신 도착정보 스냅샷
Elasticsearch = 장기 분석용 로그 저장소
```

## 4. 수집 스케줄 기준

스케줄러는 30초마다 실행되지만, 실제 수집 여부는 시간대 정책에 따라 결정된다.

| 시간대 | 정책 |
|---|---|
| 01:00 ~ 05:30 | 운영 종료 시간, 수집 중단 |
| 07:00 ~ 09:00 | 출근 시간, 1분 주기 수집 |
| 18:00 ~ 20:00 | 퇴근 시간, 1분 주기 수집 |
| 그 외 | 일반 시간, 2분 주기 수집 |

30초마다 스케줄러가 깨어나지만, 출퇴근 시간에는 2번 중 1번만 실행하고, 일반 시간에는 4번 중 1번만 실행한다.

## 5. ELK 로그 수집 구조

백엔드는 주요 동작을 구조화된 로그로 남긴다.

Logstash는 이 로그를 받아 Elasticsearch의 `subway-logs-*` 인덱스에 저장한다.

AI 서비스는 이 로그를 분석해 이상 여부를 판단한다.

주요 로그 이벤트는 다음과 같다.

| 이벤트 타입 | 의미 |
|---|---|
| `API_COLLECTION` | 외부 서울 지하철 API 호출 성공/실패 |
| `TRAFFIC` | 백엔드 API 요청 처리 로그 |
| `SCHEDULER` | 수집 스케줄러 실행 로그 |
| `SYSTEM_FETCH_ERROR` | 수집/저장 중 시스템 예외 |
| `METRIC_COLLECTION` | 수집 결과 메트릭 |
| `STATION_CONGESTION_ALERT` | 역별 열차 밀집 감지 |
| `USER_STATION_VIEW` | 로그인 사용자의 역 상세 조회 행동 |

### 5.1 Golden Signals 수집 항목

Google SRE에서 제시하는 네 가지 주요 모니터링 지표인 latency, traffic, errors, saturation을 실제 서비스 로그로 수집한다.

분 단위로 `TRAFFIC` 요약 로그를 남기며, 개별 API 요청 로그와 함께 Elasticsearch에 저장된다.

| Golden Signal | 의미 | 실제 수집 필드 |
|---|---|---|
| Latency | 요청 처리 지연 | `elapsed_ms`, `avg_elapsed_ms`, `duration_ms` |
| Traffic | 서비스 요청량 | `request_count`, `requests_per_second`, `endpoint` |
| Errors | 실패율과 오류 | `success`, `error_count`, `error_rate`, `error_msg` |
| Saturation | 시스템 포화도 | `cpu_percent`, `memory_percent`, `queue_depth`, `max_concurrent_requests`, `in_flight_requests` |

요약 로그 예시는 다음과 같다.

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
instance_count=1
```

이 로그를 통해 AI Agent는 실제 운영 중 발생한 요청량, 오류율, 지연 시간, CPU/메모리 포화도를 함께 분석할 수 있다.

## 6. AI 이상탐지 분석 흐름

AI 이상탐지는 `ai_service`에서 수행한다.

기본 분석 구간은 최근 30분이다.

```text
LOOKBACK_MINUTES=30
```

분석 흐름은 다음과 같다.

```text
1. Elasticsearch에서 최근 30분 로그 조회
2. 로그를 event_type별로 분류
3. API 오류율, 트래픽 요청량, 스케줄러 실패 건수, 수집량 계산
4. 기준값과 비교
5. 위험 / 주의 / 정상 판단
6. 판단 근거와 추천 조치사항 생성
7. subway-anomaly-results 인덱스에 저장
8. 관리자 대시보드에서 최신 결과 표시
```

## 7. 이상탐지 판단 기준

현재 코드 기준 임계값은 다음과 같다.

| 항목 | 기준 | 판단 |
|---|---:|---|
| 외부 API 오류율 | 20% 이상 | 위험 |
| 외부 API 오류율 | 5% 이상 | 주의 |
| 트래픽 요청량 | 최근 분석 구간 1,000건 이상 | 위험 |
| 스케줄러 실패 | 1건 이상 | 위험 |
| 위 조건 없음 | 정상 |

판단 우선순위는 다음과 같다.

```text
API 오류 급증
-> 트래픽 급증
-> 스케줄러 실패
-> API 오류 증가
-> 정상
```

예를 들어 API 오류율이 30%이면 트래픽이나 스케줄러보다 먼저 `서울 실시간 도착 API 응답 장애`로 판단한다.

## 8. 이상탐지 유형별 설명

### 8.1 API 오류 장애

외부 서울 지하철 API 호출 로그인 `API_COLLECTION`을 기준으로 판단한다.

```text
API 오류율 = 실패 API 호출 수 / 전체 API 호출 수
```

위험 기준은 20% 이상이다.

주의 기준은 5% 이상이다.

발생 시 추천 조치사항은 다음과 같다.

- 서울교통공사 API 응답 상태와 호출 제한 확인
- 실패 요청에 지수 백오프 재시도 적용
- 마지막 정상 데이터 캐시 적용
- HTTP 상태 코드와 timeout 유형별 장애 범위 확인

### 8.2 트래픽 급증

백엔드 컨트롤러 요청 로그인 `TRAFFIC`을 기준으로 판단한다.

최근 분석 구간에서 요청량이 1,000건 이상이면 위험으로 판단한다.

함께 보는 지표는 다음과 같다.

- 총 요청량
- 최대 RPS
- 최대 CPU 사용률
- 가동 인스턴스 수

발생 시 추천 조치사항은 다음과 같다.

- 백엔드 인스턴스 수평 확장
- 로드밸런서로 요청 분산
- 최근 도착정보 응답 캐시 적용
- CPU 또는 요청량 기준 자동 확장 정책 설정
- DB 연결 풀 한도 점검

현재 프로젝트는 자동으로 서버를 확장하지는 않는다.

현재 구현 범위는 트래픽 이상을 감지하고, 수평 확장이 필요하다는 판단과 조치사항을 관리자에게 제공하는 단계이다.

### 8.3 스케줄러 장애

`SCHEDULER` 로그 또는 `SYSTEM_FETCH_ERROR` 로그를 기준으로 판단한다.

스케줄러 실패가 1건 이상 발생하면 위험으로 판단한다.

발생 시 추천 조치사항은 다음과 같다.

- 스케줄러 예외 로그 확인
- 외부 API 연결 상태 확인
- 수집 실패 구간 재실행
- 누락 데이터 여부 점검
- 반복 실패 시 스케줄러 프로세스 재시작

### 8.4 정상 상태

다음 조건을 모두 만족하면 정상으로 판단한다.

```text
API 오류율이 기준 이내
트래픽 요청량이 기준 이내
스케줄러 오류 없음
```

정상 상태에서는 `특이 이상 없음`으로 표시된다.

## 9. AI 분석 모드

AI 서비스는 두 가지 분석 모드를 지원한다.

### 9.1 rules 모드

```text
ANALYSIS_MODE=rules
```

정해진 임계값 기반으로 안정적으로 판단한다.

발표나 시연에서는 결과가 예측 가능하므로 이 모드가 적합하다.

### 9.2 llm 모드

```text
ANALYSIS_MODE=llm
```

OpenAI 모델이 로그 메트릭을 보고 자연어 설명을 생성할 수 있다.

단, API 키와 네트워크 상태의 영향을 받으므로 발표 시연에서는 `rules` 모드가 더 안전하다.

## 10. 관리자 대시보드 기능

관리자 대시보드에서는 다음 정보를 확인할 수 있다.

- 현재 시스템 상태
- 오늘 탐지된 이상 건수
- 최근 이상 탐지 시각
- AI 인사이트 요약
- 탐지된 이상 목록
- 이상 상세 설명
- AI 판단 근거
- 추천 조치사항
- 관련 메트릭 추이 그래프

상태는 다음 세 단계로 표시된다.

```text
정상
주의
위험
```

관리자 권한이 없는 사용자는 관리자 페이지에 접근할 수 없다.

## 11. 사용자 기능

현재 사용자 기능은 다음과 같다.

- 회원가입
- 일반 로그인
- Google OAuth 로그인
- 일반 사용자 / 관리자 권한 구분
- 역 검색
- 역 상세 도착정보 조회
- 즐겨찾기 추가/삭제
- 즐겨찾기 역 목록 표시
- 사용자별 역 조회 행동 로그 수집
- 요일/시간대 기반 개인화 도착 알림

## 12. 즐겨찾기 기능

로그인 사용자는 역을 즐겨찾기할 수 있다.

즐겨찾기 정보는 MySQL의 `user_station_favorite` 테이블에 저장된다.

```text
user_id
station_id
station_name
created_at
```

즐겨찾기 목록은 메인 화면에 별도 섹션으로 표시된다.

즐겨찾기 버튼은 로그인한 사용자에게만 표시된다.

## 13. 사용자 행동 로그

로그인 사용자가 역 상세 페이지를 조회하면 백엔드가 `USER_STATION_VIEW` 로그를 남긴다.

예시는 다음과 같다.

```text
event_type=USER_STATION_VIEW
user_id=2
station_id=1001000128
station_name=동대문
day_of_week=MONDAY
hour_of_day=13
is_favorite=true
duration_ms=...
result_count=...
```

이 로그는 MySQL이 아니라 Elasticsearch에 저장된다.

이후 개인화 알림을 만들 때 이 로그를 집계한다.

## 14. 개인화 도착 알림 기준

개인화 알림은 사용자의 즐겨찾기 역과 조회 패턴을 기준으로 생성된다.

기준은 다음과 같다.

| 조건 | 기준 |
|---|---|
| 즐겨찾기 여부 | 즐겨찾기한 역만 사용 |
| 분석 기간 | 최근 30일 |
| 요일/시간대 | 현재 요일 + 현재 시간과 일치 |
| 반복 조회 | 같은 요일/시간대 3회 이상 |
| 도착 조건 | 15분 이내 도착 예정 열차 있음 |

예시는 다음과 같다.

```text
월요일 13시에 동대문을 자주 확인함
최근 30일 동안 월요일 13시에 3회 이상 조회함
동대문에 15분 이내 도착 열차가 있음
=> 인앱 알림 표시
```

첫 구현은 푸시 알림이나 문자 알림이 아니라 웹 화면 안에서 보여주는 인앱 알림이다.

## 15. 현재 가능한 주요 기능

현재 프로젝트에서 가능한 기능은 다음과 같다.

1. 실시간 1호선 노선도 표시
2. 역 검색
3. 역 클릭 후 도착정보 확인
4. 무정차 통과 상태 표시
5. 로그인 / 회원가입
6. Google OAuth 로그인
7. 관리자 권한 분리
8. 관리자 페이지 접근 제어
9. 즐겨찾기 추가/삭제
10. 즐겨찾기 역 섹션 표시
11. 사용자별 역 조회 행동 로그 수집
12. 요일/시간대 기반 도착 알림
13. ELK 기반 로그 수집
14. Kibana 로그 확인
15. AI 이상탐지 대시보드
16. API 장애 탐지
17. 트래픽 급증 탐지
18. 스케줄러 장애 탐지
19. 이상 상세 근거 표시
20. 추천 조치사항 표시
21. Elasticsearch 스냅샷 백업

## 16. 시연 명령어

### 16.1 현재 로그 기준 AI 이상탐지 1회 실행

```bash
scripts/run_ai_once_docker.sh
```

이 명령은 외부 포트를 열지 않고 `subway_ai_model` 컨테이너 내부에서 Elasticsearch에 접근한다.

```text
subway_ai_model -> elasticsearch:9200
```

### 16.2 트래픽 급증 시나리오

```bash
scripts/run_anomaly_demo.sh traffic-spike
```

관리자 대시보드에서 `접속 트래픽 급증 및 처리 용량 위험` 상태를 확인할 수 있다.

### 16.3 API 장애 시나리오

```bash
scripts/run_anomaly_demo.sh api-failure
```

관리자 대시보드에서 `서울 실시간 도착 API 응답 장애` 상태를 확인할 수 있다.

### 16.4 스케줄러 장애 시나리오

```bash
scripts/run_anomaly_demo.sh scheduler-failure
```

관리자 대시보드에서 `수집 스케줄러 실행 실패` 상태를 확인할 수 있다.

### 16.5 정상 상태 복구

```bash
scripts/run_anomaly_demo.sh restore
```

현재 live 로그 기준으로 다시 분석하고 대시보드를 복구한다.

### 16.6 즐겨찾기 알림 검증 데이터 유지

```bash
DEMO_REFRESH_SECONDS=60 scripts/run_favorite_alert_demo.sh watch
```

현재 요일과 시간대에 맞는 즐겨찾기 알림 검증 데이터를 계속 갱신한다.

종료는 `Ctrl + C`로 한다.

검증 데이터 정리는 다음 명령을 사용한다.

```bash
scripts/run_favorite_alert_demo.sh cleanup
```

## 17. 발표용 핵심 멘트

이 프로젝트는 단순히 지하철 도착정보를 보여주는 서비스가 아니라, 백엔드 수집 상태와 API 장애, 트래픽 급증, 스케줄러 실패를 ELK 로그 기반으로 분석하고, AI가 위험 상태와 조치사항을 관리자에게 제공하는 관제 시스템이다.

동시에 사용자의 역 조회 패턴을 로그로 수집해, 자주 보는 요일과 시간대에 즐겨찾기 역 도착 알림을 제공하는 개인화 기능까지 구현했다.

## 18. 구현 범위와 한계

현재 구현된 범위는 다음과 같다.

- 실시간 도착정보 조회
- 최신 도착정보 저장
- ELK 로그 수집
- AI 이상탐지
- 관리자 대시보드
- 사용자 인증
- 즐겨찾기
- 인앱 개인화 알림

아직 구현되지 않은 범위는 다음과 같다.

- 실제 서버 자동 수평 확장
- 푸시 알림
- 문자 알림
- 이메일 알림
- 장기 도착정보 이력 저장
- 운영 환경용 보안 인증이 적용된 Elasticsearch/Kibana

트래픽 급증 시 현재 시스템은 자동으로 서버를 늘리지는 않는다.

현재는 트래픽 이상을 감지하고, 수평 확장과 로드밸런싱이 필요하다는 조치사항을 관리자에게 제안하는 단계이다.

## 19. 참고자료

보고서나 발표 자료에서는 Wikipedia보다 공식 문서, 공공데이터 포털, 기업 공식 기술 문서, 학술 논문을 사용하는 것이 적합하다.

### 19.1 공공 교통 데이터

- 서울 열린데이터광장, `서울시 지하철 실시간 도착정보`
  - URL: https://data.seoul.go.kr/dataList/OA-12764/F/1/datasetView.do
  - 활용 근거:
    - 서울특별시가 제공하는 공식 공공데이터이다.
    - 데이터 분류는 `교통`이다.
    - 관련 태그에 지하철역, 도착, 상행선, 하행선, 도착예정시간, 열차번호 등이 포함되어 있어 본 프로젝트의 실시간 도착정보 수집 목적과 직접적으로 연결된다.
    - 실시간 데이터는 API 방식으로 제공되며, 과거 데이터는 별도 적재가 어렵다는 설명이 있어 본 프로젝트가 MySQL에는 최신 상태만 저장하고 Elasticsearch에는 로그를 저장하는 구조를 선택한 근거로 활용할 수 있다.

### 19.2 실시간 대중교통 데이터 표준

- Google for Developers, `GTFS Realtime Overview`
  - URL: https://developers.google.com/transit/gtfs-realtime
  - 활용 근거:
    - GTFS Realtime은 대중교통 기관이 실시간 지연, 차량 위치, 서비스 알림 등을 애플리케이션에 제공하기 위한 공식 사양이다.
    - 실시간 도착/출발 정보와 서비스 알림이 사용자 경험을 향상시킨다는 설명이 있어 본 프로젝트의 실시간 지하철 도착정보 제공 필요성을 설명하는 근거로 사용할 수 있다.
    - Trip updates, Service alerts, Vehicle positions를 지원하므로 본 프로젝트의 도착정보, 이상 상태, 알림 기능과 비교할 수 있다.

### 19.3 Observability와 로그 기반 모니터링

- Elastic, `Elastic Observability`
  - URL: https://www.elastic.co/observability
  - 활용 근거:
    - Elastic은 로그, 메트릭, 트레이스를 하나의 관측 데이터로 통합해 시스템 상태를 분석하는 Observability 플랫폼을 제공한다.
    - 로그, 메트릭, 트레이스를 기반으로 문제 해결, 근본 원인 분석, 알림, 대시보드 구성을 지원한다.
    - 본 프로젝트의 Logstash, Elasticsearch, Kibana 기반 로그 수집 및 관리자 대시보드 구조와 직접적으로 관련된다.

- Elastic Docs, `Anomaly detection with machine learning`
  - URL: https://www.elastic.co/docs/explore-analyze/machine-learning/anomaly-detection
  - 활용 근거:
    - Elastic 공식 문서는 시계열 데이터를 분석해 데이터셋의 비정상 패턴을 식별할 수 있다고 설명한다.
    - 본 프로젝트는 Elastic의 내장 ML 기능을 그대로 사용하지는 않지만, Elasticsearch에 저장된 시계열 로그를 AI Agent가 분석해 이상 상태를 판단한다는 점에서 같은 문제 영역에 속한다.

### 19.4 AIOps와 AI 기반 운영 자동화

- IBM, `What is AIOps?`
  - URL: https://www.ibm.com/think/topics/aiops
  - 활용 근거:
    - IBM은 AIOps를 AI, 자연어 처리, 머신러닝을 활용해 IT 운영과 서비스 관리 워크플로를 자동화, 간소화, 최적화하는 개념으로 설명한다.
    - AIOps가 대량의 운영 데이터, 시스템 로그, 메트릭을 수집하고 이상 이벤트를 식별하며 원인 분석과 조치 제안을 수행한다는 설명은 본 프로젝트의 AI 이상탐지 구조와 직접적으로 연결된다.
    - 본 프로젝트의 AI Agent는 API 오류율, 트래픽 요청량, 스케줄러 실패 로그를 분석해 상태를 판단하고 조치사항을 제공하므로 AIOps의 축소 구현 사례로 설명할 수 있다.

### 19.5 학술 자료

- Lingzhe Zhang et al., `A Survey of AIOps for Failure Management in the Era of Large Language Models`, arXiv, 2024
  - URL: https://arxiv.org/abs/2406.11213
  - 활용 근거:
    - LLM 시대의 AIOps와 장애 관리 연구 동향을 정리한 서베이 논문이다.
    - AIOps가 대규모 소프트웨어 시스템의 장애 관리, 고가용성, 신뢰성 확보를 위해 활용된다는 점을 설명하는 학술 근거로 사용할 수 있다.
    - 본 프로젝트의 로그 기반 장애 탐지와 AI Agent 기반 조치사항 생성 방향을 설명하는 배경 자료로 적합하다.

### 19.6 유사 서비스의 운영 관제 동향

네이버맵, 카카오맵, 구글맵과 같은 대규모 지도 및 모빌리티 서비스가 내부적으로 어떤 관제 도구를 사용하는지는 대부분 공개되어 있지 않다.

따라서 보고서에서는 특정 기업이 `ELK와 AI를 사용한다`고 단정하기보다, 공개 자료로 확인 가능한 범위에서 다음과 같이 설명하는 것이 안전하다.

```text
네이버맵, 카카오맵, 구글맵과 같은 지도 및 모빌리티 서비스는 실시간 위치, 경로, 교통, 도착정보와 같이 지속적으로 변하는 데이터를 제공해야 하므로, 장애 감지와 운영 관제가 중요하다. 다만 각 기업의 내부 관제 도구와 AI 적용 방식은 공개 범위가 제한적이기 때문에, 본 보고서에서는 Google SRE, Uber 실시간 데이터 인프라, Elastic Observability, IBM AIOps와 같은 공개 자료를 바탕으로 대규모 실시간 서비스에서 로그·메트릭 기반 관제와 AI 기반 이상탐지가 중요해지고 있음을 근거로 삼는다.
```

#### Google SRE 사례

- Google, `Site Reliability Engineering - Monitoring Distributed Systems`
  - URL: https://sre.google/sre-book/monitoring-distributed-systems/
  - 활용 근거:
    - Google SRE 문서는 대규모 분산 시스템 운영에서 모니터링과 알림이 필수적이라고 설명한다.
    - 모니터링은 시스템의 query count, error count, processing time 같은 실시간 정량 데이터를 수집, 처리, 집계, 표시하는 활동으로 정의된다.
    - 서비스 대시보드는 핵심 메트릭을 요약해서 보여주며, 대표적인 모니터링 지표로 latency, traffic, errors, saturation의 네 가지 golden signals를 제시한다.
    - 본 프로젝트의 AI 이상탐지 기준인 API 응답시간, 트래픽 요청량, 오류율, 처리 용량 위험은 Google SRE의 golden signals와 대응된다.

Google SRE의 네 가지 golden signals와 본 프로젝트 지표를 연결하면 다음과 같다.

| Google SRE 지표 | 의미 | 본 프로젝트 대응 지표 |
|---|---|---|
| Latency | 요청 처리 시간 | API 평균/최대 응답시간, 스케줄러 수행시간 |
| Traffic | 시스템에 들어오는 요청량 | 백엔드 요청량, 요청 수, RPS |
| Errors | 실패 요청 비율 | 외부 API 오류율, 스케줄러 실패 |
| Saturation | 시스템 포화 상태 | 트래픽 임계치 초과, CPU, 단일 인스턴스 처리 위험 |

#### Uber 실시간 모빌리티 데이터 인프라 사례

- Yupeng Fu, Chinmay Soman, `Real-time Data Infrastructure at Uber`, arXiv, 2021
  - URL: https://arxiv.org/abs/2104.00087
  - 활용 근거:
    - Uber는 승객, 운전자, 음식 주문 등 실시간성이 강한 데이터를 대량으로 수집하고, 초 단위 의사결정이 필요한 모빌리티 플랫폼이다.
    - 논문은 Uber가 실시간 데이터 인프라를 구축하고, 엔지니어, 데이터 과학자, 운영 담당자 등 다양한 사용자에게 실시간 데이터를 제공해야 하는 복잡성을 설명한다.
    - 이는 본 프로젝트가 실시간 지하철 도착정보를 수집하고 운영 대시보드와 사용자 알림으로 연결하는 구조와 유사한 문제 영역이다.

#### Elastic Observability와 AIOps 동향

- Elastic, `Elastic Observability`
  - URL: https://www.elastic.co/observability
  - 활용 근거:
    - Elastic은 logs, metrics, traces를 통합해 실시간 시스템 모델을 만들고, AI가 이를 기반으로 문제를 분석할 수 있다고 설명한다.
    - 로그 분석, 인프라 모니터링, APM, 분산 추적, 알림, AI 기반 조사 기능을 제공한다.
    - 본 프로젝트의 ELK 로그 수집, Kibana 확인, AI Agent 분석 구조와 기술 방향이 유사하다.

- IBM, `What is AIOps?`
  - URL: https://www.ibm.com/think/topics/aiops
  - 활용 근거:
    - IBM은 AIOps가 대량의 운영 데이터, 로그, 메트릭을 수집하고, 중요한 이벤트와 패턴을 식별하며, 원인 분석과 조치 제안을 수행한다고 설명한다.
    - 본 프로젝트의 AI Agent는 최근 로그를 기반으로 API 장애, 트래픽 급증, 스케줄러 실패를 탐지하고 조치사항을 제안하므로 AIOps 개념을 소규모 도메인에 적용한 사례로 설명할 수 있다.

#### 보고서 작성 시 주의할 표현

다음 표현은 공개 근거가 부족하므로 피하는 것이 좋다.

```text
네이버맵과 카카오맵은 ELK와 AI를 이용해 운영 관제를 수행한다.
구글맵은 ELK 기반 AI 이상탐지를 사용한다.
```

대신 다음처럼 쓰는 것이 안전하다.

```text
대규모 지도 및 모빌리티 서비스는 실시간 데이터 제공과 장애 대응을 위해 운영 관제가 필수적이다. Google SRE 문서는 대규모 분산 시스템에서 latency, traffic, errors, saturation과 같은 핵심 지표를 기반으로 모니터링해야 한다고 설명한다. 또한 Uber의 실시간 데이터 인프라 사례는 모빌리티 서비스에서 대량의 실시간 데이터를 수집하고 운영 및 의사결정에 활용하는 구조가 필요함을 보여준다. 최근에는 Elastic Observability와 IBM AIOps처럼 로그, 메트릭, 트레이스를 통합하고 AI를 활용해 이상탐지와 원인 분석을 지원하는 기술이 확산되고 있다. 본 프로젝트는 이러한 흐름을 지하철 실시간 도착정보 서비스에 적용한 사례이다.
```

## 20. 참고자료 활용 예시 문장

보고서의 `국내외 현황` 또는 `개발의 필요성`에는 다음과 같은 방식으로 활용할 수 있다.

```text
서울특별시는 서울 열린데이터광장을 통해 지하철 실시간 도착정보를 공공데이터로 제공하고 있으며, 해당 데이터에는 역, 상하행, 도착예정시간, 열차번호 등 실시간 도착 안내에 필요한 정보가 포함된다. 그러나 실시간 데이터는 API 방식으로 제공되며 과거 데이터를 별도로 제공하지 않는 특성이 있어, 서비스 운영자는 별도의 저장 및 로그 분석 구조를 설계할 필요가 있다.
```

```text
국외에서는 GTFS Realtime과 같은 실시간 대중교통 데이터 사양이 활용되고 있으며, 이는 지연, 차량 위치, 서비스 알림 등 실시간 상태 정보를 애플리케이션에 전달하기 위한 표준적 접근 방식이다. 이는 대중교통 서비스에서 실시간 정보 제공과 알림 기능이 사용자 경험 향상에 중요한 요소임을 보여준다.
```

```text
운영 관점에서는 AIOps와 Observability 기술이 확산되고 있다. IBM은 AIOps를 운영 데이터, 로그, 메트릭을 분석해 이상 이벤트를 식별하고 원인 분석과 조치 제안을 수행하는 기술로 설명한다. Elastic 역시 로그, 메트릭, 트레이스를 통합해 시스템 상태를 분석하고 이상 패턴을 탐지하는 Observability 구조를 강조한다. 본 프로젝트는 이러한 흐름을 지하철 실시간 도착정보 서비스에 적용해, API 장애, 트래픽 급증, 스케줄러 실패를 자동으로 탐지하는 구조를 구현하였다.
```
