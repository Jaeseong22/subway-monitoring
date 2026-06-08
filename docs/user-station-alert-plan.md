# 요일/시간대 기반 즐겨찾기 역 알림 기능 계획

## Summary

회원이 역을 즐겨찾기하고, 즐겨찾기한 역을 자주 확인하는 요일/시간대를 ELK 로그로 수집한다. 이후 해당 요일/시간대에 즐겨찾기 역의 열차 도착 정보가 있으면 사용자에게 인앱 알림 후보를 제공한다.

## Key Changes

### 1. 즐겨찾기 기능

- MySQL에 사용자별 즐겨찾기 역을 저장한다.
- API:
  - `GET /api/v1/users/me/favorites`
  - `POST /api/v1/users/me/favorites/{stationId}`
  - `DELETE /api/v1/users/me/favorites/{stationId}`
- 로그인 사용자만 사용할 수 있다.
- 역 상세 화면과 역 미리보기 카드에 즐겨찾기 버튼을 표시한다.
- 메인 화면에 즐겨찾기 역 섹션을 표시한다.

### 2. ELK 사용자 행동 로그

- 역 상세 조회 요청에 로그인 토큰을 포함한다.
- 백엔드 `ArrivalController.getStationArrivals()`에서 토큰을 선택적으로 해석한다.
- ELK로 들어가는 로그 이벤트는 `USER_STATION_VIEW`로 기록한다.
- 전체 도착정보 polling 로그는 사용자 관심 로그로 사용하지 않는다.

로그 필드:

```text
event_type=USER_STATION_VIEW
user_id=2 | anonymous
station_id=1001000133
station_name=서울역
day_of_week=MONDAY
hour_of_day=8
is_favorite=true | false
duration_ms=...
result_count=...
```

### 3. 요일/시간대별 선호 패턴 집계

- Elasticsearch `subway-logs-*`에서 최근 30일 기준으로 집계한다.
- 기준은 `day_of_week + hour_of_day`이다.
- 즐겨찾기한 역만 알림 후보로 사용한다.
- API:
  - `GET /api/v1/users/me/station-patterns?days=30`

### 4. 즐겨찾기 역 도착 알림

- API:
  - `GET /api/v1/users/me/arrival-alerts`
- 조건:
  - 사용자가 즐겨찾기한 역
  - 현재 요일과 현재 시간대가 과거 자주 본 패턴과 일치
  - 해당 역에 15분 이내 도착 예정 열차가 있음
- 기본 기준:
  - 최근 30일
  - 같은 `day_of_week + hour_of_day`에 3회 이상 조회
  - 도착 예정 시간 15분 이내

### 5. 프론트 UI

- 로그인 사용자에게만 즐겨찾기 버튼을 표시한다.
- 메인 화면에 `즐겨찾기 역` 섹션을 추가한다.
- 메인 화면 상단에 개인화 알림 카드를 표시한다.
- 알림 클릭 시 해당 역 상세 화면으로 이동한다.
- 알림 후보가 없으면 알림 UI는 표시하지 않는다.

## Test Plan

- 즐겨찾기 API:
  - 토큰 없음: `401`
  - 즐겨찾기 추가/삭제/목록 조회 성공
  - 같은 역 중복 추가 시 기존 항목 유지
- ELK 로그:
  - 비로그인 역 조회: `user_id=anonymous`
  - 로그인 역 조회: `user_id`, `station_id`, `day_of_week`, `hour_of_day`, `is_favorite` 기록
  - Logstash를 통해 `subway-logs-*` 인덱스 적재 확인
- 패턴 집계:
  - 최근 30일 같은 요일/시간대 조회 3회 이상이면 패턴 반환
  - 즐겨찾기하지 않은 역은 알림 후보에서 제외
- 알림 API:
  - 현재 요일/시간대와 패턴이 일치하고 15분 이내 열차가 있으면 알림 반환
  - 조건 미충족 시 빈 배열 반환
- 프론트:
  - 로그인 사용자만 즐겨찾기/알림 UI 확인 가능
  - 알림 클릭 시 역 상세로 이동
  - 기존 관리자 로그인/관제 요약 접근 유지

## Assumptions

- 첫 버전의 알림은 푸시/문자/이메일이 아닌 인앱 알림이다.
- 사용자 행동 분석 저장소는 MySQL이 아니라 ELK 로그이다.
- MySQL은 즐겨찾기 상태 저장에만 사용한다.
- 요일 기준은 `MONDAY`~`SUNDAY`, 시간대 기준은 0~23시 정각 단위이다.
- 알림 기준은 최근 30일, 같은 요일/시간대 3회 이상, 15분 이내 도착 열차이다.
