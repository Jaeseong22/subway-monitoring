import React from 'react';
import { ArrivalInfo } from '../types';
import { ArrivalTopCard } from './ArrivalTopCard';
import { AlertCircle, Moon } from 'lucide-react';
import { getScheduleMode } from '../utils/arrival';
interface ArrivalGridProps {
  direction: string;
  arrivals: ArrivalInfo[];
}
export const ArrivalGrid: React.FC<ArrivalGridProps> = ({
  direction,
  arrivals
}) => {
  const isOff = getScheduleMode() === 'off';
  return (
    <div className="mb-8">
      <div className="flex items-center gap-3 mb-4">
        <h3 className="text-xl font-bold text-gray-900">{direction}</h3>
        <div className="h-px bg-gray-200 flex-1" />
      </div>

      {arrivals.length > 0 ?
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {arrivals.map((arrival, index) =>
        <ArrivalTopCard
          key={`${arrival.btrainNo}-${arrival.ordkey}`}
          arrival={arrival}
          index={index} />

        )}
        </div> :

      <div className="bg-gray-50 rounded-2xl border border-gray-200 border-dashed p-8 flex flex-col items-center justify-center text-center">
          <div className="w-12 h-12 bg-gray-100 rounded-full flex items-center justify-center mb-3">
            {isOff ?
          <Moon className="text-gray-400" size={24} /> :

          <AlertCircle className="text-gray-400" size={24} />
          }
          </div>
          <p className="text-gray-600 font-medium">
            {isOff ?
          '현재 열차 운행이 종료된 시간입니다' :
          '현재 도착 예정인 열차가 없습니다'}
          </p>
          <p className="text-sm text-gray-400 mt-1">
            {isOff ?
          '운행 시작 시간에 자동으로 정보가 갱신됩니다' :
          '잠시 후 다시 확인해주세요'}
          </p>
        </div>
      }
    </div>);

};