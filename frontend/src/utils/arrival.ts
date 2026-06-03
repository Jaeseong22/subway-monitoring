import { ArrivalInfo, ScheduleMode } from '../types';

/** Convert barvlDt (seconds string) to user-friendly time */
/** Convert barvlDt (seconds string) and arvlMsg2 to user-friendly time */
export function formatArrivalTime(barvlDt: string, arvlMsg2: string): string {
  // 1. Try to extract from arvlMsg2 (Highest Priority)
  if (arvlMsg2) {
    if (arvlMsg2.includes('진입') || arvlMsg2.includes('곧 도착')) return '곧 도착';
    if (arvlMsg2.includes('도착')) return '도착';
    if (arvlMsg2.includes('전역 출발')) return '1역 전';
    
    // Parse "[n]번째 전역" -> "n역 전"
    const stationMatch = arvlMsg2.match(/\[(\d+)\]번째 전역/);
    if (stationMatch) return `${stationMatch[1]}역 전`;
    
    // If it mentions specific station but not in brackets
    if (arvlMsg2.includes('전역')) return '1역 전';
  }

  // 2. Fallback to barvlDt (seconds)
  const sec = parseInt(barvlDt, 10);
  if (isNaN(sec) || sec <= 0) return arvlMsg2 || '정보 없음';
  
  const min = Math.floor(sec / 60);
  if (min < 1) return '곧 도착';
  return `${min}분 후`;
}

/** Get arrival seconds as number */
export function getArrivalSec(barvlDt: string): number {
  return parseInt(barvlDt, 10) || 0;
}

/** Determine display train type from btrainSttus + lstcarAt */
export function getTrainTypeLabel(arrival: ArrivalInfo): string {
  if (arrival.lstcarAt === '1') return '막차';
  if (arrival.btrainSttus === '급행') return '급행';
  if (arrival.btrainSttus === 'ITX') return 'ITX';
  return '일반';
}

/** Get badge variant for train type */
export function getTrainBadgeVariant(
  arrival: ArrivalInfo
): 'express' | 'itx' | 'last' | 'normal' {
  if (arrival.lstcarAt === '1') return 'last';
  if (arrival.btrainSttus === '급행') return 'express';
  if (arrival.btrainSttus === 'ITX') return 'itx';
  return 'normal';
}

/** Convert updnLine code to display string */
export function getDirectionLabel(updnLine: string): string {
  return updnLine === '0' ? '상행' : '하행';
}

/** Convert arvlCd to user-friendly status */
export function getArvlStatusText(arvlCd: string): string {
  switch (arvlCd) {
    case '0': return '진입';
    case '1': return '도착';
    case '2': return '출발';
    case '3': return '전역출발';
    case '4': return '전역진입';
    case '5': return '전역도착';
    case '99': return '운행중';
    default: return '';
  }
}

/** Determine current schedule mode based on time */
export function getScheduleMode(date?: Date): ScheduleMode {
  const now = date || new Date();
  const h = now.getHours();
  const m = now.getMinutes();
  const totalMin = h * 60 + m;

  if (totalMin < 330) return 'off';
  if (h >= 7 && h < 9) return 'rush';
  if (totalMin >= 330) return 'normal';
  return 'off';
}

/** Get schedule mode display info */
export function getScheduleInfo(mode: ScheduleMode): {
  label: string;
  description: string;
  interval: string;
  color: string;
} {
  switch (mode) {
    case 'rush':
      return {
        label: '1분 주기 갱신 중',
        description: '출근 시간대에는 더 자주 업데이트됩니다',
        interval: '1분',
        color: 'emerald'
      };
    case 'normal':
      return {
        label: '2분 주기 갱신 중',
        description: '현재 운영 시간에 맞춰 자동 갱신 중입니다',
        interval: '2분',
        color: 'blue'
      };
    case 'off':
      return {
        label: '자동 갱신 일시 중단',
        description: '열차 운행이 종료된 시간입니다',
        interval: '-',
        color: 'gray'
      };
  }
}

/** Format recptnDt to display time */
export function formatRecptnDt(recptnDt: string): string {
  if (!recptnDt) return '';
  const parts = recptnDt.split(' ');
  if (parts.length >= 2) {
    const timeParts = parts[1].split(':');
    if (timeParts.length >= 2) return `${timeParts[0]}:${timeParts[1]}`;
  }
  return recptnDt;
}

/** Filter arrivals for a specific station, direction, sorted by arrival time, limited by distance */
export function filterAndSortArrivals(
  arrivals: ArrivalInfo[],
  statnId: string,
  updnLine: string,
  limit: number = 3
): ArrivalInfo[] {
  return arrivals
    .filter((a) => {
      // Basic filter by station ID and direction
      return a.statnId === statnId && a.updnLine === updnLine;
    })
    .sort((a, b) => getArrivalSec(a.barvlDt) - getArrivalSec(b.barvlDt))
    .slice(0, limit);
}

/** Get the first arrival for a station + direction */
export function getFirstArrival(
  arrivals: ArrivalInfo[],
  statnId: string,
  updnLine: string
): ArrivalInfo | undefined {
  return filterAndSortArrivals(arrivals, statnId, updnLine, 1)[0];
}