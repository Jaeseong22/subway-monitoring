import React from 'react';
import { motion } from 'framer-motion';

interface SummaryCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ReactNode;
  colorClass: string;
  delay?: number;
}

const iconBgMap: Record<string, string> = {
  'text-red-600': 'bg-red-50',
  'text-amber-600': 'bg-amber-50',
  'text-emerald-600': 'bg-emerald-50',
  'text-blue-600': 'bg-blue-50',
  'text-purple-600': 'bg-purple-50',
  'text-orange-600': 'bg-orange-50',
  'text-gray-900': 'bg-gray-100'
};

export const SummaryCard: React.FC<SummaryCardProps> = ({
  title,
  value,
  subtitle,
  icon,
  colorClass,
  delay = 0
}) => {
  const iconBg = iconBgMap[colorClass] || 'bg-gray-100';

  return (
    <motion.div
      initial={{
        opacity: 0,
        y: 20
      }}
      animate={{
        opacity: 1,
        y: 0
      }}
      transition={{
        delay
      }}
      className="bg-white rounded-2xl p-6 border border-gray-200 shadow-sm flex items-start justify-between">
      
      <div>
        <p className="text-sm font-medium text-gray-500 mb-1">{title}</p>
        <h3 className={`text-3xl font-black tracking-tight ${colorClass}`}>
          {value}
        </h3>
        {subtitle && <p className="text-sm text-gray-400 mt-1">{subtitle}</p>}
      </div>
      <div className={`p-3 rounded-xl ${iconBg}`}>
        {icon}
      </div>
    </motion.div>);

};