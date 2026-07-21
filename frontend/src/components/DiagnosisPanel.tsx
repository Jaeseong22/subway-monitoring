import React from 'react';
import { motion } from 'framer-motion';
import { Brain, Search, Target, CheckCircle2, ShieldQuestion } from 'lucide-react';
import { Diagnosis, Verification } from '../types';

interface DiagnosisPanelProps {
  diagnosis: Diagnosis | null;
  verification: Verification | null;
}

const CONFIDENCE_STYLE: Record<string, string> = {
  high: 'bg-emerald-100 text-emerald-700 border-emerald-200',
  medium: 'bg-amber-100 text-amber-700 border-amber-200',
  low: 'bg-gray-100 text-gray-600 border-gray-200'
};

const CONFIDENCE_LABEL: Record<string, string> = {
  high: '높음', medium: '보통', low: '낮음'
};

const VERDICT_STYLE: Record<string, { label: string; className: string }> = {
  real: { label: '실제 이상', className: 'bg-red-50 text-red-700 border-red-200' },
  false_positive: { label: '오탐 의심', className: 'bg-amber-50 text-amber-700 border-amber-200' },
  uncertain: { label: '판단 보류', className: 'bg-gray-50 text-gray-500 border-gray-200' }
};

/**
 * AI 에이전트가 스스로 로그를 파고들어 찾은 근본 원인과, 여러 심사관이 교차검증한
 * 결과를 보여준다. 진단이 없거나(정상/rules 모드) 생략된 경우 안내를 띄운다.
 */
export const DiagnosisPanel: React.FC<DiagnosisPanelProps> = ({ diagnosis, verification }) => {
  // available·상태 가드를 통과한 값만 아래에서 쓰도록 좁힌다(non-null 단언 회피).
  const dx = diagnosis?.available && diagnosis.status !== '생략' ? diagnosis : null;
  const vp = verification?.available && verification.totalVotes > 0 ? verification : null;

  if (!dx && !vp) {
    return (
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6">
        <div className="flex items-center gap-2 mb-2">
          <Brain size={18} className="text-purple-600" />
          <h2 className="font-bold text-gray-900">AI 근본 원인 분석</h2>
        </div>
        <p className="text-sm text-gray-400">
          현재 확정된 이상이 없거나, AI 진단이 비활성(rules 모드) 상태입니다. 이상이
          감지되면 AI 에이전트가 로그를 조사해 근본 원인을 여기에 표시합니다.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* 검증 패널 결과 */}
      {vp &&
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <ShieldQuestion size={18} className="text-blue-600" />
            <h2 className="font-bold text-gray-900">검증 패널 (교차검증)</h2>
          </div>
          {vp.downgraded &&
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border bg-amber-100 text-amber-700 border-amber-200">
              오탐으로 강등됨
            </span>
          }
        </div>
        <p className="text-sm text-gray-600 mb-4">{vp.summary}</p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {vp.votes.map((vote) => {
            const style = VERDICT_STYLE[vote.verdict] ?? VERDICT_STYLE.uncertain;
            return (
              <div key={vote.lens} className={`rounded-xl border p-3 ${style.className}`}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-bold">{vote.name}</span>
                  <span className="text-xs font-semibold">{style.label}</span>
                </div>
                <p className="text-xs opacity-80">{vote.reason}</p>
              </div>
            );
          })}
        </div>
      </motion.div>
      }

      {/* 근본 원인 진단 (RCA) */}
      {dx &&
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.05 }}
        className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Brain size={18} className="text-purple-600" />
            <h2 className="font-bold text-gray-900">AI 근본 원인 분석</h2>
            {dx.status === '미결' &&
            <span className="text-xs text-gray-400">(원인 미특정)</span>
            }
          </div>
          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${
          CONFIDENCE_STYLE[dx.confidence] ?? CONFIDENCE_STYLE.low}`
          }>
            신뢰도 {CONFIDENCE_LABEL[dx.confidence] ?? dx.confidence}
          </span>
        </div>

        {/* 결론 */}
        <div className="bg-purple-50/50 border border-purple-100 rounded-xl p-4 mb-4">
          <div className="flex items-start gap-2">
            <Target size={16} className="text-purple-500 shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-semibold text-purple-900 mb-1">근본 원인</p>
              <p className="text-sm text-gray-700">{dx.rootCause}</p>
            </div>
          </div>
        </div>

        {/* 조사 과정 — 에이전트가 실제로 호출한 도구 */}
        {dx.steps.length > 0 &&
        <div className="mb-4">
          <div className="flex items-center gap-2 mb-2">
            <Search size={14} className="text-gray-400" />
            <span className="text-xs font-semibold text-gray-500">
              AI 조사 과정 ({dx.stepsUsed}단계)
            </span>
          </div>
          <ol className="space-y-2 border-l-2 border-purple-100 pl-3">
            {dx.steps.map((step, idx) =>
            <li key={idx} className="text-xs">
              <span className="font-mono text-purple-600">{step.tool}</span>
              <p className="text-gray-500 mt-0.5">{step.observation}</p>
            </li>
            )}
          </ol>
        </div>
        }

        {/* 근거 */}
        {dx.evidence.length > 0 &&
        <div className="mb-4">
          <p className="text-xs font-semibold text-gray-500 mb-2">판단 근거</p>
          <ul className="space-y-1">
            {dx.evidence.map((item, idx) =>
            <li key={idx} className="text-xs text-gray-600 bg-gray-50 rounded-md px-3 py-2 border border-gray-100">
              {item}
            </li>
            )}
          </ul>
        </div>
        }

        {/* 먼저 확인할 것 */}
        {dx.recommendedFocus &&
        <div className="flex items-start gap-2 text-sm text-emerald-800 bg-emerald-50/50 border border-emerald-100 rounded-lg p-3">
          <CheckCircle2 size={16} className="text-emerald-500 shrink-0 mt-0.5" />
          <div>
            <span className="font-semibold">먼저 확인: </span>
            {dx.recommendedFocus}
          </div>
        </div>
        }
      </motion.div>
      }
    </div>
  );
};
