import React from 'react';
interface StatusBadgeProps {
  type: 'train' | 'severity' | 'system';
  status: string;
  className?: string;
}
export const StatusBadge: React.FC<StatusBadgeProps> = ({
  type,
  status,
  className = ''
}) => {
  let bgColor = 'bg-gray-100';
  let textColor = 'text-gray-800';
  let borderColor = 'border-transparent';
  if (type === 'train') {
    switch (status) {
      case '급행':
        bgColor = 'bg-rose-100';
        textColor = 'text-rose-700';
        borderColor = 'border-rose-200';
        break;
      case 'ITX':
        bgColor = 'bg-orange-100';
        textColor = 'text-orange-700';
        borderColor = 'border-orange-200';
        break;
      case '막차':
        bgColor = 'bg-purple-100';
        textColor = 'text-purple-700';
        borderColor = 'border-purple-200';
        break;
      case '일반':
      default:
        bgColor = 'bg-gray-100';
        textColor = 'text-gray-600';
        borderColor = 'border-gray-200';
        break;
    }
  } else if (type === 'severity' || type === 'system') {
    switch (status) {
      case '위험':
        bgColor = 'bg-red-100';
        textColor = 'text-red-700';
        borderColor = 'border-red-200';
        break;
      case '주의':
        bgColor = 'bg-amber-100';
        textColor = 'text-amber-700';
        borderColor = 'border-amber-200';
        break;
      case '정상':
        bgColor = 'bg-emerald-100';
        textColor = 'text-emerald-700';
        borderColor = 'border-emerald-200';
        break;
    }
  }
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${bgColor} ${textColor} ${borderColor} ${className}`}>
      
      {status}
    </span>);

};