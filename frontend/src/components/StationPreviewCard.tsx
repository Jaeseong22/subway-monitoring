import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Station, ArrivalInfo } from '../types';
import { ChevronRight, ArrowRight, Star } from 'lucide-react';
import { motion } from 'framer-motion';
import {
  formatArrivalTime,
  getTrainTypeLabel,
  formatRecptnDt } from
'../utils/arrival';
import { UpdateStatusBadge } from './UpdateStatusBadge';
interface StationPreviewCardProps {
  station: Station;
  upArrival?: ArrivalInfo;
  downArrival?: ArrivalInfo;
  onClose?: () => void;
  isAuthenticated?: boolean;
  isFavorite?: boolean;
  onToggleFavorite?: (stationId: string) => void;
}
function ArrivalSummaryRow({
  label,
  arrival



}: {label: string;arrival?: ArrivalInfo;}) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-gray-500 font-medium flex items-center gap-1">
        {label} <ArrowRight size={12} />
      </span>
      {arrival ?
      <div className="text-right flex items-center gap-2">
          <span className="font-bold text-gray-900">
            {formatArrivalTime(arrival.barvlDt, arrival.arvlMsg2)}
          </span>
          <span className="text-gray-600 text-xs">{arrival.bstatnNm}행</span>
          {getTrainTypeLabel(arrival) !== '일반' &&
        <span
          className={`text-[10px] px-1.5 py-0.5 rounded-full font-semibold ${getTrainTypeLabel(arrival) === '급행' ? 'bg-rose-100 text-rose-700' : getTrainTypeLabel(arrival) === 'ITX' ? 'bg-orange-100 text-orange-700' : 'bg-purple-100 text-purple-700'}`}>
          
              {getTrainTypeLabel(arrival)}
            </span>
        }
        </div> :

      <span className="text-gray-400 text-xs">정보 없음</span>
      }
    </div>);

}
export const StationPreviewCard: React.FC<StationPreviewCardProps> = ({
  station,
  upArrival,
  downArrival,
  isAuthenticated = false,
  isFavorite = false,
  onToggleFavorite
}) => {
  const navigate = useNavigate();
  const latestRecptnDt = upArrival?.recptnDt || downArrival?.recptnDt;
  return (
    <motion.div
      initial={{
        opacity: 0,
        x: 20
      }}
      animate={{
        opacity: 1,
        x: 0
      }}
      exit={{
        opacity: 0,
        x: 20
      }}
      className="bg-white rounded-2xl shadow-xl border border-gray-100 overflow-hidden w-80 flex flex-col">
      
      <div className="bg-line1 px-5 py-4 text-white relative">
        <div className="flex items-center justify-between gap-3 mb-1">
          <div className="flex items-center gap-2 min-w-0">
            <span className="w-5 h-5 rounded-full bg-white text-line1 flex items-center justify-center text-xs font-bold">
              1
            </span>
            <h3 className="text-xl font-bold truncate">{station.name}</h3>
          </div>
          {isAuthenticated &&
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              onToggleFavorite?.(station.id);
            }}
            className="p-1.5 rounded-full bg-white/15 hover:bg-white/25 transition-colors"
            title={isFavorite ? '즐겨찾기 해제' : '즐겨찾기 추가'}>
            <Star
              size={17}
              className={isFavorite ? 'fill-yellow-300 text-yellow-300' : 'text-white'} />
          </button>
          }
        </div>
        <p className="text-blue-100 text-sm opacity-90">{station.nameEn}</p>

        {station.hasTransfer &&
        <div className="flex gap-1 mt-3">
            {station.transferLines.map((line) =>
          <span
            key={line}
            className="text-[10px] px-1.5 py-0.5 bg-white/20 rounded-sm font-medium">
            
                {line}
              </span>
          )}
          </div>
        }
      </div>

      <div className="p-5 flex-1 flex flex-col gap-3">
        {/* Update status */}
        <div className="flex items-center justify-between">
          <UpdateStatusBadge />
          {latestRecptnDt &&
          <span className="text-[10px] text-gray-400">
              갱신 {formatRecptnDt(latestRecptnDt)}
            </span>
          }
        </div>

        {/* Arrival summaries */}
        <div className="space-y-3">
          <ArrivalSummaryRow label="상행" arrival={upArrival} />
          <div className="h-px bg-gray-100 w-full" />
          <ArrivalSummaryRow label="하행" arrival={downArrival} />
        </div>

        <p className="text-[10px] text-gray-400 leading-relaxed">
          수집 주기에 따라 실제 도착 시각과 다를 수 있습니다
        </p>

        <div className="mt-auto pt-2">
          <button
            onClick={() => navigate(`/station/${station.id}`)}
            className="w-full py-2.5 bg-gray-50 hover:bg-gray-100 text-gray-900 rounded-xl font-medium text-sm flex items-center justify-center gap-1 transition-colors border border-gray-200">
            
            상세 정보 보기 <ChevronRight size={16} />
          </button>
        </div>
      </div>
    </motion.div>);

};
