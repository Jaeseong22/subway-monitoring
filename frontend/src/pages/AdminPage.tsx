import React, { useEffect, useMemo, useState } from 'react';
import { Header } from '../components/Header';
import { SummaryCard } from '../components/SummaryCard';
import { InsightCard } from '../components/InsightCard';
import { StatusBadge } from '../components/StatusBadge';
import { Anomaly } from '../types';
import { useAdminData } from '../hooks/useAdminData';
import {
  ShieldAlert,
  Activity,
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  Clock } from
'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine } from
'recharts';
import { motion, AnimatePresence } from 'framer-motion';

const parseApiDate = (value: string) => {
  if (!value) return null;
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(value);
  const parsed = new Date(hasTimezone ? value : `${value}Z`);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
};

export const AdminPage: React.FC = () => {
  const { anomalies, insights, summary, isLoading } = useAdminData();
  const [selectedAnomaly, setSelectedAnomaly] = useState<Anomaly | null>(null);

  useEffect(() => {
    if (!selectedAnomaly && anomalies.length > 0) {
      setSelectedAnomaly(anomalies[0]);
    }
  }, [anomalies, selectedAnomaly]);

  const derivedCounts = useMemo(() => {
    const criticalCount = summary?.criticalCount ?? anomalies.filter((a) => a.severity === '위험').length;
    const warningCount = summary?.warningCount ?? anomalies.filter((a) => a.severity === '주의').length;
    const todayCount = summary?.todayAnomalyCount ?? anomalies.length;
    return { criticalCount, warningCount, todayCount };
  }, [anomalies, summary]);

  const systemStatus = summary?.systemStatus
    || (derivedCounts.criticalCount > 0 ? '위험' : derivedCounts.warningCount > 0 ? '주의' : '정상');

  const latestTitle = summary?.latestAnomalyTitle || selectedAnomaly?.type || '특이 이상 없음';
  const latestAt = summary?.latestAnomalyAt || selectedAnomaly?.detectedAt || '';
  const latestLabel = useMemo(() => {
    if (!latestAt) return '알 수 없음';
    const parsed = parseApiDate(latestAt);
    if (!parsed) return '알 수 없음';
    const diffMs = Date.now() - parsed.getTime();
    const diffMinutes = Math.floor(diffMs / 60000);
    if (diffMinutes < 1) return '방금 전';
    if (diffMinutes < 60) return `${diffMinutes}분 전`;
    const diffHours = Math.floor(diffMinutes / 60);
    if (diffHours < 24) return `${diffHours}시간 전`;
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays}일 전`;
  }, [latestAt]);
  const getStatusColor = (status: string) => {
    if (status === '위험') return 'text-red-600';
    if (status === '주의') return 'text-amber-600';
    return 'text-emerald-600';
  };
  const getStatusIcon = (status: string) => {
    if (status === '위험')
    return <ShieldAlert size={24} className="text-red-600" />;
    if (status === '주의')
    return <AlertTriangle size={24} className="text-amber-600" />;
    return <CheckCircle2 size={24} className="text-emerald-600" />;
  };
  return (
    <div className="min-h-screen flex flex-col bg-gray-50">
      <Header />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900 mb-2">
            AI 이상탐지 요약
          </h1>
          <p className="text-gray-500">
            ELK/Kibana 로그 기반 실시간 서비스 상태 분석
          </p>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
          <SummaryCard
            title="현재 시스템 상태"
            value={systemStatus}
            icon={getStatusIcon(systemStatus)}
            colorClass={getStatusColor(systemStatus)}
            delay={0} />
          
          <SummaryCard
            title="오늘 탐지된 이상 건수"
            value={derivedCounts.todayCount}
            subtitle={`위험 ${derivedCounts.criticalCount}건 / 주의 ${derivedCounts.warningCount}건`}
            icon={<Activity size={24} className="text-blue-600" />}
            colorClass="text-gray-900"
            delay={0.1} />
          
          <SummaryCard
            title="최근 이상 탐지"
            value={latestLabel}
            subtitle={latestTitle}
            icon={<Clock size={24} className="text-purple-600" />}
            colorClass="text-gray-900"
            delay={0.2} />
        </div>

        {/* AI Insights */}
        <div className="mb-8">
          <h2 className="text-lg font-bold text-gray-900 mb-4">
            AI 인사이트 요약
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {insights.map((insight, idx) =>
              <InsightCard key={insight.id} insight={insight} index={idx} />
            )}
            {!isLoading && insights.length === 0 && (
              <div className="text-sm text-gray-400">AI 인사이트가 없습니다.</div>
            )}
          </div>
        </div>

        {/* Main Content: List + Detail */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Alert List */}
          <div className="lg:col-span-1 bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden flex flex-col h-[600px]">
            <div className="p-4 border-b border-gray-200 bg-gray-50">
              <h2 className="font-bold text-gray-900">탐지된 이상 현상</h2>
            </div>
            <div className="flex-1 overflow-y-auto p-2">
              {anomalies.map((anomaly) =>
              <div
                key={anomaly.id}
                onClick={() => setSelectedAnomaly(anomaly)}
                className={`p-4 rounded-xl mb-2 cursor-pointer transition-all border ${selectedAnomaly?.id === anomaly.id ? 'bg-blue-50 border-blue-200 shadow-sm' : 'bg-white border-transparent hover:bg-gray-50'}`}>
                
                  <div className="flex justify-between items-start mb-2">
                    <StatusBadge type="severity" status={anomaly.severity} />
                    <span className="text-xs text-gray-400">
                      {parseApiDate(anomaly.detectedAt)?.toLocaleTimeString(
                      'ko-KR',
                      {
                        hour: '2-digit',
                        minute: '2-digit'
                      }
                    ) ?? '알 수 없음'}
                    </span>
                  </div>
                  <h3
                  className={`font-bold mb-1 ${selectedAnomaly?.id === anomaly.id ? 'text-blue-900' : 'text-gray-900'}`}>
                  
                    {anomaly.type}
                  </h3>
                  <p className="text-xs text-gray-500 line-clamp-1">
                    {anomaly.impactScope}
                  </p>
                </div>
              )}
              {!isLoading && anomalies.length === 0 && (
                <div className="text-center text-sm text-gray-400 py-6">
                  최근 분석 결과가 없습니다.
                </div>
              )}
            </div>
          </div>

          {/* Detail Panel */}
          <div className="lg:col-span-2 bg-white rounded-2xl border border-gray-200 shadow-sm p-6 h-[600px] overflow-y-auto">
            <AnimatePresence mode="wait">
              {selectedAnomaly ?
              <motion.div
                key={selectedAnomaly.id}
                initial={{
                  opacity: 0,
                  y: 10
                }}
                animate={{
                  opacity: 1,
                  y: 0
                }}
                exit={{
                  opacity: 0,
                  y: -10
                }}
                className="space-y-6">
                
                  <div className="flex items-start justify-between border-b border-gray-100 pb-4">
                    <div>
                      <div className="flex items-center gap-3 mb-2">
                        <StatusBadge
                        type="severity"
                        status={selectedAnomaly.severity} />
                      
                        <h2 className="text-2xl font-bold text-gray-900">
                          {selectedAnomaly.type}
                        </h2>
                      </div>
                      <p className="text-gray-500">
                        발생 시각:{' '}
                        {parseApiDate(selectedAnomaly.detectedAt)?.toLocaleString(
                        'ko-KR'
                      ) ?? '알 수 없음'}
                      </p>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div className="space-y-4">
                      <div>
                        <h3 className="text-sm font-bold text-gray-900 mb-2 flex items-center gap-2">
                          <AlertTriangle size={16} className="text-amber-500" />{' '}
                          현상 설명
                        </h3>
                        <p className="text-sm text-gray-600 bg-gray-50 p-3 rounded-lg border border-gray-100">
                          {selectedAnomaly.description}
                        </p>
                      </div>
                      <div>
                        <h3 className="text-sm font-bold text-gray-900 mb-2 flex items-center gap-2">
                          <Activity size={16} className="text-blue-500" /> AI
                          판단 근거
                        </h3>
                        {selectedAnomaly.evidence?.length > 0 ? (
                          <ul className="space-y-2">
                            {selectedAnomaly.evidence.map((item, idx) => (
                              <li
                                key={idx}
                                className="text-sm text-gray-700 bg-blue-50/50 p-3 rounded-lg border border-blue-100">
                                {item}
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <p className="text-sm text-gray-600 bg-blue-50/50 p-3 rounded-lg border border-blue-100">
                            {selectedAnomaly.reasoning}
                          </p>
                        )}
                      </div>
                    </div>

                    <div>
                      <h3 className="text-sm font-bold text-gray-900 mb-2 flex items-center gap-2">
                        <CheckCircle2 size={16} className="text-emerald-500" />{' '}
                        추천 조치사항
                      </h3>
                      <ul className="space-y-2">
                        {selectedAnomaly.recommendedActions.map(
                        (action, idx) =>
                        <li
                          key={idx}
                          className="flex items-start gap-2 text-sm text-gray-700 bg-emerald-50/50 p-3 rounded-lg border border-emerald-100">
                          
                              <ChevronRight
                            size={16}
                            className="text-emerald-500 shrink-0 mt-0.5" />
                          
                              {action}
                            </li>

                      )}
                      </ul>
                    </div>
                  </div>

                  <div className="mt-8">
                    <h3 className="text-sm font-bold text-gray-900 mb-4">
                      관련 메트릭 추이
                    </h3>
                    {selectedAnomaly.metrics.length > 0 ? (
                      <div className="h-64 w-full bg-gray-50 rounded-xl p-4 border border-gray-100">
                        <ResponsiveContainer width="100%" height="100%">
                          <LineChart data={selectedAnomaly.metrics}>
                            <CartesianGrid
                            strokeDasharray="3 3"
                            vertical={false}
                            stroke="#E5E7EB" />
                          
                            <XAxis
                            dataKey="time"
                            axisLine={false}
                            tickLine={false}
                            tick={{
                              fontSize: 12,
                              fill: '#6B7280'
                            }} />
                          
                            <YAxis
                            axisLine={false}
                            tickLine={false}
                            tick={{
                              fontSize: 12,
                              fill: '#6B7280'
                            }} />
                          
                            <Tooltip
                            contentStyle={{
                              borderRadius: '8px',
                              border: 'none',
                              boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)'
                            }} />
                          
                            {selectedAnomaly.metrics[0]?.baseline !== undefined && (
                              <ReferenceLine
                              y={selectedAnomaly.metrics[0].baseline}
                              stroke="#EF4444"
                              strokeDasharray="3 3"
                              label={{
                                position: 'insideTopLeft',
                                value: '임계치',
                                fill: '#EF4444',
                                fontSize: 12
                              }} />
                            )}
                          
                            <Line
                            type="monotone"
                            dataKey="value"
                            stroke="#3B82F6"
                            strokeWidth={3}
                            dot={{
                              r: 4,
                              strokeWidth: 2
                            }}
                            activeDot={{
                              r: 6,
                              strokeWidth: 0
                            }} />
                          
                          </LineChart>
                        </ResponsiveContainer>
                      </div>
                    ) : (
                      <div className="text-sm text-gray-400 bg-gray-50 border border-gray-100 rounded-xl p-4">
                        해당 이상 탐지에 대한 메트릭 추이가 없습니다.
                      </div>
                    )}
                  </div>
                </motion.div> :

              <div className="h-full flex flex-col items-center justify-center text-gray-400">
                  <Activity size={48} className="mb-4 opacity-20" />
                  <p>좌측 목록에서 분석할 항목을 선택하세요</p>
                </div>
              }
            </AnimatePresence>
          </div>
        </div>
      </main>
    </div>);

};
