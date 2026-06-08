import React, { useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Header } from '../components/Header';
import { ArrivalGrid } from '../components/ArrivalGrid';
import { ServiceNoticeBanner } from '../components/ServiceNoticeBanner';
import { stations } from '../data/mockData';
import { ArrowLeft, Map, Info, Star } from 'lucide-react';
import { motion } from 'framer-motion';
import { filterAndSortArrivals } from '../utils/arrival';
import { useArrivals } from '../hooks/useArrivals';
import { useAuth } from '../context/AuthContext';
import { useFavoriteStations } from '../hooks/useFavoriteStations';

export const StationDetailPage: React.FC = () => {
  const { id } = useParams<{
    id: string;
  }>();
  const navigate = useNavigate();
  const station = stations.find((s) => s.id === id);
  const { arrivals: stationArrivals } = useArrivals(id);
  const { isAuthenticated } = useAuth();
  const { isFavorite, toggleFavorite } = useFavoriteStations();

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [id]);

  if (!station) {
    return (
      <div className="min-h-screen flex flex-col bg-gray-50">
        <Header />
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <h2 className="text-2xl font-bold text-gray-900 mb-2">
              역을 찾을 수 없습니다
            </h2>
            <button
              onClick={() => navigate('/')}
              className="text-line1 hover:underline">
              
              메인으로 돌아가기
            </button>
          </div>
        </div>
      </div>);

  }

  const upArrivals = filterAndSortArrivals(stationArrivals, id!, '0', 3);
  const downArrivals = filterAndSortArrivals(stationArrivals, id!, '1', 3);
  // Get latest recptnDt from any arrival for this station
  const latestRecptnDt =
  stationArrivals.length > 0 ? stationArrivals[0].recptnDt : undefined;
  return (
    <div className="min-h-screen flex flex-col bg-gray-50">
      <Header />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Station Header */}
        <motion.div
          initial={{
            opacity: 0,
            y: -20
          }}
          animate={{
            opacity: 1,
            y: 0
          }}
          className="bg-white rounded-3xl p-6 md:p-8 shadow-sm border border-gray-200 mb-6 relative overflow-hidden">
          
          <div className="absolute top-0 left-0 w-full h-2 bg-line1" />

          <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
            <div className="flex items-start gap-4">
              <button
                onClick={() => navigate('/')}
                className="mt-1.5 p-2 bg-gray-50 hover:bg-gray-100 rounded-full text-gray-500 transition-colors">
                
                <ArrowLeft size={20} />
              </button>
              <div>
                <div className="flex items-center gap-3 mb-1">
                  <span className="w-8 h-8 rounded-full bg-line1 text-white flex items-center justify-center text-sm font-bold shadow-md">
                    1
                  </span>
                  <h1 className="text-4xl font-extrabold text-gray-900 tracking-tight">
                    {station.name}
                  </h1>
                </div>
                <p className="text-gray-500 font-medium ml-11">
                  {station.nameEn}
                </p>
              </div>
            </div>

            <div className="flex flex-col items-end gap-2">
              {isAuthenticated &&
              <button
                type="button"
                onClick={() => toggleFavorite(station.id)}
                className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl border text-sm font-semibold transition-colors ${
                  isFavorite(station.id)
                    ? 'bg-yellow-50 border-yellow-200 text-yellow-700'
                    : 'bg-gray-50 border-gray-200 text-gray-600 hover:bg-gray-100'
                }`}>
                <Star
                  size={17}
                  className={isFavorite(station.id) ? 'fill-yellow-400 text-yellow-400' : 'text-gray-400'} />
                {isFavorite(station.id) ? '즐겨찾기됨' : '즐겨찾기'}
              </button>
              }
              {station.hasTransfer &&
              <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-500 font-medium">
                    환승 노선:
                  </span>
                  <div className="flex gap-1.5">
                    {station.transferLines.map((line) =>
                  <span
                    key={line}
                    className="px-2 py-1 bg-gray-100 text-gray-700 text-xs font-bold rounded-md border border-gray-200">
                    
                        {line}
                      </span>
                  )}
                  </div>
                </div>
              }
            </div>
          </div>
        </motion.div>

        {/* Service Notice Banner */}
        <ServiceNoticeBanner
          lastRecptnDt={latestRecptnDt}
          variant="banner"
          className="mb-6" />
        

        {/* Arrivals Section */}
        <div className="space-y-8 mb-12">
          <ArrivalGrid
            direction="상행 (소요산/청량리 방면)"
            arrivals={upArrivals} />
          
          <ArrivalGrid
            direction="하행 (인천/신창 방면)"
            arrivals={downArrivals} />
          
        </div>

        {/* Station Info Section */}
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
            delay: 0.2
          }}
          className="grid grid-cols-1 md:grid-cols-2 gap-6">
          
          <div className="bg-white rounded-2xl p-6 border border-gray-200 shadow-sm">
            <div className="flex items-center gap-2 mb-4">
              <Info className="text-line1" size={20} />
              <h3 className="text-lg font-bold text-gray-900">역 정보</h3>
            </div>
            <p className="text-gray-600 leading-relaxed">
              {station.description}
            </p>
          </div>

          <div className="bg-white rounded-2xl p-6 border border-gray-200 shadow-sm">
            <div className="flex items-center gap-2 mb-4">
              <Map className="text-line1" size={20} />
              <h3 className="text-lg font-bold text-gray-900">
                주변 주요 시설
              </h3>
            </div>
            <ul className="space-y-2">
              {station.landmarks.map((landmark, idx) =>
              <li key={idx} className="flex items-center gap-2 text-gray-600">
                  <div className="w-1.5 h-1.5 rounded-full bg-gray-300" />
                  {landmark}
                </li>
              )}
              {station.landmarks.length === 0 &&
              <li className="text-gray-400">등록된 주요 시설이 없습니다.</li>
              }
            </ul>
          </div>
        </motion.div>
      </main>
    </div>);

};
