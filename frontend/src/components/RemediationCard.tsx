import React, { useState } from 'react';
import { motion } from 'framer-motion';
import {
  ArrowRight,
  Check,
  ChevronDown,
  ChevronUp,
  CircleAlert,
  Loader2,
  RotateCcw,
  Server,
  ShieldOff,
  X } from
'lucide-react';
import { RemediationAction } from '../types';

interface RemediationCardProps {
  action: RemediationAction;
  index: number;
  isBusy: boolean;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
}

const STATUS_STYLE: Record<string, { label: string; className: string }> = {
  PENDING: { label: '승인 대기', className: 'bg-amber-100 text-amber-700 border-amber-200' },
  APPROVED: { label: '승인됨 · 실행 대기', className: 'bg-blue-100 text-blue-700 border-blue-200' },
  EXECUTING: { label: '실행 중', className: 'bg-blue-100 text-blue-700 border-blue-200' },
  EXECUTED: { label: '실행 완료 · 검증 대기', className: 'bg-indigo-100 text-indigo-700 border-indigo-200' },
  SUCCEEDED: { label: '성공', className: 'bg-emerald-100 text-emerald-700 border-emerald-200' },
  FAILED: { label: '실패', className: 'bg-red-100 text-red-700 border-red-200' },
  ROLLED_BACK: { label: '롤백됨', className: 'bg-orange-100 text-orange-700 border-orange-200' },
  REJECTED: { label: '거부됨', className: 'bg-gray-100 text-gray-600 border-gray-200' },
  EXPIRED: { label: '만료됨', className: 'bg-gray-100 text-gray-600 border-gray-200' }
};

const formatTime = (value: string) => {
  if (!value) return '';
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(value);
  const parsed = new Date(hasTimezone ? value : `${value}Z`);
  return Number.isNaN(parsed.getTime())
    ? ''
    : parsed.toLocaleString('ko-KR', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      });
};

export const RemediationCard: React.FC<RemediationCardProps> = ({
  action,
  index,
  isBusy,
  onApprove,
  onReject
}) => {
  const [showHistory, setShowHistory] = useState(false);
  const [confirming, setConfirming] = useState(false);

  const status = STATUS_STYLE[action.status] ?? {
    label: action.status,
    className: 'bg-gray-100 text-gray-600 border-gray-200'
  };
  const isPending = action.status === 'PENDING';
  const isScaleOut = action.kind === 'scale_out';

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
      className={`bg-white rounded-xl border shadow-sm p-4 ${
      action.blocked ? 'border-red-200' : 'border-gray-200'}`
      }>

      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-2 flex-wrap">
          <span
            className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${status.className}`}>
            {status.label}
          </span>
          {action.rollback &&
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold border bg-orange-50 text-orange-700 border-orange-200">
              <RotateCcw size={12} /> 롤백
            </span>
          }
          {action.dryRun &&
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border bg-slate-100 text-slate-600 border-slate-200">
              dry-run
            </span>
          }
        </div>
        <span className="text-xs text-gray-400 shrink-0">
          {formatTime(action.createdAt)}
        </span>
      </div>

      {/* 무엇을 하는 조치인가 */}
      <div className="flex items-center gap-3 mb-3">
        <Server size={18} className={isScaleOut ? 'text-blue-600' : 'text-gray-500'} />
        <div className="flex items-center gap-2 font-bold text-gray-900">
          <span className="text-sm text-gray-500">{action.service}</span>
          <span className="text-lg">{action.fromReplicas ?? '?'}대</span>
          <ArrowRight size={16} className="text-gray-400" />
          <span className={`text-lg ${isScaleOut ? 'text-blue-600' : 'text-gray-600'}`}>
            {action.toReplicas ?? '?'}대
          </span>
        </div>
      </div>

      <p className="text-sm text-gray-600 mb-3">{action.reason}</p>

      {action.blocked &&
      <div className="flex items-start gap-2 text-sm text-red-700 bg-red-50 border border-red-100 rounded-lg p-3 mb-3">
          <ShieldOff size={16} className="shrink-0 mt-0.5" />
          <span>자동으로 대응할 수 없는 상태입니다. 사람의 판단이 필요합니다.</span>
        </div>
      }

      {action.signalKeys.length > 0 &&
      <div className="flex items-center gap-2 flex-wrap mb-3">
          <span className="text-xs text-gray-400">촉발 신호</span>
          {action.signalKeys.map((key) =>
        <span
          key={key}
          className="px-2 py-0.5 rounded-md text-xs font-medium bg-gray-100 text-gray-600 border border-gray-200">
              {key}
            </span>
        )}
        </div>
      }

      {action.evidence.length > 0 &&
      <ul className="space-y-1 mb-3">
          {action.evidence.slice(0, 3).map((item, idx) =>
        <li key={idx} className="text-xs text-gray-500 bg-gray-50 rounded-md px-3 py-2 border border-gray-100">
              {item}
            </li>
        )}
        </ul>
      }

      {/* 승인/거부 */}
      {isPending && !action.blocked &&
      <div className="border-t border-gray-100 pt-3 mt-3">
          {confirming ?
        <div className="space-y-2">
              <div className="flex items-start gap-2 text-sm text-amber-800 bg-amber-50 border border-amber-100 rounded-lg p-3">
                <CircleAlert size={16} className="shrink-0 mt-0.5" />
                <span>
                  승인하면 실행 워커가 <strong>{action.service}</strong>를{' '}
                  <strong>{action.toReplicas}대</strong>로 조정합니다. 실제 인프라가 변경됩니다.
                </span>
              </div>
              <div className="flex gap-2">
                <button
              type="button"
              disabled={isBusy}
              onClick={() => {
                setConfirming(false);
                onApprove(action.id);
              }}
              className="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 transition-colors">
                  {isBusy ? <Loader2 size={16} className="animate-spin" /> : <Check size={16} />}
                  실행 승인
                </button>
                <button
              type="button"
              disabled={isBusy}
              onClick={() => setConfirming(false)}
              className="px-4 py-2 rounded-lg text-sm font-semibold text-gray-600 bg-gray-100 hover:bg-gray-200 disabled:opacity-50 transition-colors">
                  취소
                </button>
              </div>
            </div> :

        <div className="flex gap-2">
              <button
            type="button"
            disabled={isBusy}
            onClick={() => setConfirming(true)}
            className="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 transition-colors">
                <Check size={16} /> 승인
              </button>
              <button
            type="button"
            disabled={isBusy}
            onClick={() => onReject(action.id)}
            className="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold text-gray-700 bg-gray-100 hover:bg-gray-200 disabled:opacity-50 transition-colors">
                {isBusy ? <Loader2 size={16} className="animate-spin" /> : <X size={16} />}
                거부
              </button>
            </div>
        }
        </div>
      }

      {/* 처리 이력 */}
      {action.history.length > 0 &&
      <div className="border-t border-gray-100 pt-2 mt-3">
          <button
          type="button"
          onClick={() => setShowHistory((prev) => !prev)}
          className="inline-flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 transition-colors">
            처리 이력 {action.history.length}건
            {showHistory ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
          {showHistory &&
        <ol className="mt-2 space-y-2 border-l-2 border-gray-100 pl-3">
              {action.history.map((entry, idx) =>
          <li key={idx} className="text-xs">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-gray-700">{entry.status}</span>
                    <span className="text-gray-400">{formatTime(entry.at)}</span>
                  </div>
                  {entry.note && <p className="text-gray-500 mt-0.5">{entry.note}</p>}
                </li>
          )}
            </ol>
        }
        </div>
      }
    </motion.div>);

};
