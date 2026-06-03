import React from 'react';
import { ArrivalInfo } from '../types';
import { StatusBadge } from './StatusBadge';
import { MapPin, TrainFront } from 'lucide-react';
import { motion } from 'framer-motion';
import {
  formatArrivalTime,
  getArrivalSec,
  getTrainTypeLabel,
  getTrainBadgeVariant,
  getArvlStatusText,
  formatRecptnDt } from
'../utils/arrival';
interface ArrivalTopCardProps {
  arrival: ArrivalInfo;
  index: number;
}
export const ArrivalTopCard: React.FC<ArrivalTopCardProps> = ({
  arrival,
  index
}) => {
  const trainType = getTrainTypeLabel(arrival);
  const badgeVariant = getTrainBadgeVariant(arrival);
  const arrivalSec = getArrivalSec(arrival.barvlDt);
  const isHighlight = badgeVariant === 'express' || badgeVariant === 'itx';
  const displayTime = formatArrivalTime(arrival.barvlDt, arrival.arvlMsg2);
  const isArrivingSoon = arrivalSec > 0 
    ? arrivalSec < 120 
    : (displayTime.includes('도착') || displayTime.includes('1역 전'));
  const statusText = getArvlStatusText(arrival.arvlCd);
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
        delay: index * 0.1
      }}
      className={`bg-white rounded-2xl p-5 border ${isHighlight ? 'border-rose-200' : 'border-gray-200'} shadow-sm hover:shadow-md transition-shadow relative overflow-hidden`}>
      
      {isHighlight &&
      <div
        className={`absolute top-0 left-0 w-1 h-full ${badgeVariant === 'itx' ? 'bg-orange-500' : 'bg-rose-500'}`} />

      }

      <div className="flex justify-between items-start mb-3">
        <div>
          <div className="flex items-center gap-2 mb-2 flex-wrap">
            <h4 className="text-lg font-bold text-gray-900">
              {arrival.bstatnNm}행 {trainType}
            </h4>
            {arrival.lstcarAt === '1' && trainType !== '막차' &&
            <StatusBadge type="train" status="막차" />
            }
          </div>
        </div>

        <div className="text-right shrink-0">
          <div
            className={`text-2xl font-black tracking-tight ${isArrivingSoon ? 'text-rose-600' : 'text-line1'}`}>
            
            {displayTime}
          </div>
        </div>
      </div>

      <div className="bg-gray-50 rounded-xl p-3 space-y-2">
        <div className="flex items-start gap-2">
          <div className="mt-0.5 w-4 flex justify-center">
            <div
              className={`w-2 h-2 rounded-full ${isArrivingSoon ? 'bg-rose-500 animate-pulse' : 'bg-line1'}`} />
            
          </div>
          <p className="text-sm font-medium text-gray-900">
            {arrival.arvlMsg2}
          </p>
        </div>
        <div className="flex items-start gap-2">
          <div className="mt-0.5 w-4 flex justify-center text-gray-400">
            <MapPin size={14} />
          </div>
          <p className="text-xs text-gray-500">{arrival.arvlMsg3}</p>
        </div>
      </div>

      <div className="flex items-center justify-between mt-3 pt-2 border-t border-gray-100">
        <div className="flex items-center gap-1.5 text-[11px] text-gray-400">
          <TrainFront size={12} />
          <span>{arrival.btrainNo}</span>
          {statusText &&
          <>
              <span className="text-gray-300">·</span>
              <span>{statusText}</span>
            </>
          }
        </div>
        {arrival.recptnDt &&
        <span className="text-[10px] text-gray-300">
            {formatRecptnDt(arrival.recptnDt)}
          </span>
        }
      </div>
    </motion.div>);

};