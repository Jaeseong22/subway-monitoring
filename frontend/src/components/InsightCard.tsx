import React from 'react';
import { AIInsight } from '../types';
import { Sparkles, TrendingUp, AlertTriangle, Activity } from 'lucide-react';
import { motion } from 'framer-motion';
interface InsightCardProps {
  insight: AIInsight;
  index: number;
}
export const InsightCard: React.FC<InsightCardProps> = ({ insight, index }) => {
  const getIcon = () => {
    switch (insight.category) {
      case 'performance':
        return <Activity size={18} className="text-blue-600" />;
      case 'error':
        return <AlertTriangle size={18} className="text-red-600" />;
      case 'traffic':
        return <TrendingUp size={18} className="text-amber-600" />;
      default:
        return <Sparkles size={18} className="text-purple-600" />;
    }
  };
  return (
    <motion.div
      initial={{
        opacity: 0,
        x: -20
      }}
      animate={{
        opacity: 1,
        x: 0
      }}
      transition={{
        delay: index * 0.1
      }}
      className="bg-gradient-to-r from-indigo-50 to-blue-50 rounded-xl p-4 border border-indigo-100 flex gap-4 items-start">
      
      <div className="bg-white p-2 rounded-lg shadow-sm shrink-0">
        {getIcon()}
      </div>
      <div>
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs font-bold text-indigo-600 bg-indigo-100 px-2 py-0.5 rounded-full">
            AI 분석
          </span>
          <span className="text-xs text-gray-500">{insight.title}</span>
        </div>
        <p className="text-sm text-gray-800 font-medium leading-relaxed">
          {insight.content}
        </p>
      </div>
    </motion.div>);

};