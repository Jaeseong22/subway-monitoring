import React, { useEffect, useState } from 'react';
import { RefreshCw, Pause, Zap } from 'lucide-react';
import { getScheduleMode, getScheduleInfo } from '../utils/arrival';
export const UpdateStatusBadge: React.FC<{
  className?: string;
}> = ({ className = '' }) => {
  const [mode, setMode] = useState(getScheduleMode());
  useEffect(() => {
    const timer = setInterval(() => setMode(getScheduleMode()), 30000);
    return () => clearInterval(timer);
  }, []);
  const info = getScheduleInfo(mode);
  const colorMap: Record<string, string> = {
    emerald: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    blue: 'bg-blue-50 text-blue-700 border-blue-200',
    gray: 'bg-gray-100 text-gray-500 border-gray-200'
  };
  const iconMap: Record<string, React.ReactNode> = {
    rush: <Zap size={12} />,
    normal:
    <RefreshCw size={12} className="animate-[spin_3s_linear_infinite]" />,

    off: <Pause size={12} />
  };
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold border ${colorMap[info.color]} ${className}`}>
      
      {iconMap[mode]}
      {info.label}
    </span>);

};