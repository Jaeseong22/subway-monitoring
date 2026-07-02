import React, { useEffect, useState } from 'react';
import { Info } from 'lucide-react';
import {
  formatRecptnDt } from
 '../utils/arrival';
import { UpdateStatusBadge } from './UpdateStatusBadge';

interface ServiceNoticeBannerProps {
  lastRecptnDt?: string;
  variant?: 'inline' | 'banner';
  className?: string;
}

export const ServiceNoticeBanner: React.FC<ServiceNoticeBannerProps> = ({
  lastRecptnDt,
  variant = 'banner',
  className = ''
}) => {
  const [systemStatus, setSystemStatus] = useState({ currentInterval: '수집 정책 확인 중...', isOperationEnded: false });

  const apiUrl = (import.meta as any).env.VITE_API_URL || 'http://localhost:8080';

  useEffect(() => {
    async function fetchSystemStatus() {
      try {
        const response = await fetch(`${apiUrl}/api/v1/system/status`);
        if (response.ok) {
          const data = await response.json();
          setSystemStatus(data);
        }
      } catch (error) {
        console.error('Failed to fetch system status:', error);
      }
    }

    fetchSystemStatus();
    const timer = setInterval(fetchSystemStatus, 60000);
    return () => clearInterval(timer);
  }, [apiUrl]);

  if (variant === 'inline') {
    return (
      <div
        className={`flex flex-wrap items-center gap-2 text-xs text-gray-500 ${className}`}>
        <UpdateStatusBadge />
        {lastRecptnDt &&
          <span className="text-gray-400">
            최근 갱신 {formatRecptnDt(lastRecptnDt)}
          </span>
        }
        <span className="text-gray-300">·</span>
        <span>실제 열차 상황에 따라 차이가 있을 수 있습니다</span>
      </div>
    );
  }

  return (
    <div className={`space-y-3 ${className}`}>
      <div className="bg-blue-50/60 border border-blue-100 rounded-xl px-4 py-3">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 shrink-0">
            <Info size={16} className="text-blue-500" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-2 mb-1">
              <span className="text-sm font-semibold text-gray-800">
                AI 관제 시스템 상태
              </span>
              <UpdateStatusBadge />
              <span className="ml-auto text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-blue-100 text-blue-600 border border-blue-200">
                {systemStatus.currentInterval}
              </span>
            </div>
            <p className="text-xs text-gray-500 leading-relaxed">
              {systemStatus.isOperationEnded ? 
                '현재 열차 운행이 종료된 시간입니다. 운행 시작 시 자동으로 수집이 재개됩니다.' :
                '실시간 데이터 수집 및 AI 이상 감지 로직이 정상 작동 중입니다.'}
            </p>
            {lastRecptnDt &&
              <p className="text-[11px] text-gray-400 mt-1">
                최근 데이터 분석 시점: {formatRecptnDt(lastRecptnDt)}
              </p>
            }
          </div>
        </div>
      </div>
    </div>
  );
};