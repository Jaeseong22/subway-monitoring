export interface Station {
  id: string;
  name: string;
  nameEn: string;
  hasTransfer: boolean;
  transferLines: string[];
  description: string;
  landmarks: string[];
}

/** Raw API response item from Seoul Metro real-time arrival API */
export interface ArrivalInfo {
  subwayId: string;
  updnLine: string; // "0": 상행/내선, "1": 하행/외선
  trainLineNm: string; // 도착지방면 (e.g. "청량리행 - 청량리방면")
  statnFid: string;
  statnTid: string;
  statnId: string;
  statnNm: string;
  trnsitCo: string;
  ordkey: string;
  subwayList: string;
  statnList: string;
  btrainSttus: string; // 열차종류: "급행", "ITX", "" (일반)
  barvlDt: string; // 도착예정시간(초), string from API
  btrainNo: string;
  bstatnId: string;
  bstatnNm: string; // 종착역명
  recptnDt: string; // 생성시각 (e.g. "2024-01-15 14:32:10")
  arvlMsg2: string; // 첫번째 도착메시지
  arvlMsg3: string; // 두번째 도착메시지
  arvlCd: string; // 도착코드: 0~5, 99
  lstcarAt: string; // 막차여부: "1" 막차, "0" 아님
  isSkipping: boolean; // 무정차 통과 여부
}

export type ScheduleMode = 'rush' | 'normal' | 'off';

export interface Anomaly {
  id: string;
  type: string;
  detectedAt: string;
  impactScope: string;
  severity: '정상' | '주의' | '위험' | string;
  description: string;
  reasoning: string;
  evidence: string[];
  recommendedActions: string[];
  metrics: {time: string;value: number;baseline?: number;}[];
}

export interface AIInsight {
  id: string;
  category?: string;
  title: string;
  content: string;
  tags?: string[];
}

export interface AdminSummary {
  systemStatus: string;
  todayAnomalyCount: number;
  criticalCount: number;
  warningCount: number;
  latestAnomalyTitle: string;
  latestAnomalyAt: string;
}

/** 자동 대응 조치의 상태 기계. 백엔드 RemediationActionDto와 동일하다. */
export type RemediationStatus =
  | 'PENDING'
  | 'APPROVED'
  | 'REJECTED'
  | 'EXECUTING'
  | 'EXECUTED'
  | 'SUCCEEDED'
  | 'FAILED'
  | 'ROLLED_BACK'
  | 'EXPIRED';

export interface RemediationHistoryEntry {
  at: string;
  status: string;
  note: string;
}

export interface RemediationAction {
  id: string;
  status: RemediationStatus | string;
  /** scale_out | scale_in */
  kind: string;
  reason: string;
  service: string;
  fromReplicas: number | null;
  toReplicas: number | null;
  createdAt: string;
  executedAt: string;
  triggerTitle: string;
  signalKeys: string[];
  evidence: string[];
  history: RemediationHistoryEntry[];
  /** 상한 도달 등 자동으로는 대응할 수 없어 기록만 남긴 조치 */
  blocked: boolean;
  /** 실패한 조치를 되돌리는 역방향 조치 */
  rollback: boolean;
  /** 워커가 dry-run 모드로 실행했는지 */
  dryRun: boolean;
}

/** 근본 원인 진단 에이전트(RCA)의 조사 한 단계 */
export interface DiagnosisStep {
  step: number;
  tool: string;
  observation: string;
}

/** 근본 원인 진단 에이전트(RCA) 결과 */
export interface Diagnosis {
  available: boolean;
  status: string; // 완료 | 미결 | 생략
  rootCause: string;
  confidence: string; // high | medium | low
  evidence: string[];
  recommendedFocus: string;
  stepsUsed: number;
  steps: DiagnosisStep[];
}

/** 검증 패널의 한 심사관 판정 */
export interface VerificationVote {
  lens: string;
  name: string;
  verdict: string; // real | false_positive | uncertain
  reason: string;
}

/** 검증 패널(멀티 에이전트) 결과 */
export interface Verification {
  available: boolean;
  falsePositiveVotes: number;
  totalVotes: number;
  downgraded: boolean;
  summary: string;
  votes: VerificationVote[];
}

export interface FavoriteStation {
  stationId: string;
  stationName: string;
  createdAt: string;
}

export interface StationPattern {
  stationId: string;
  stationName: string;
  dayOfWeek: string;
  hourOfDay: number;
  viewCount: number;
}

export interface ArrivalAlert {
  stationId: string;
  stationName: string;
  dayOfWeek: string;
  hourOfDay: number;
  message: string;
  arrivalStatusMsg: string;
  destination: string;
  expectedArrivalSeconds: number;
}
