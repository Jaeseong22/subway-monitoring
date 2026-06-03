import React, { useState, useMemo } from 'react';
import { Header } from '../components/Header';
import { SearchBar } from '../components/SearchBar';
import { StationPreviewCard } from '../components/StationPreviewCard';
import { RouteMap } from '../components/RouteMap';
import { ServiceNoticeBanner } from '../components/ServiceNoticeBanner';
import { UpdateStatusBadge } from '../components/UpdateStatusBadge';
import { stations } from '../data/mockData';
import { Station } from '../types';
import { getFirstArrival } from '../utils/arrival';
import { AnimatePresence } from 'framer-motion';
import { useGlobalArrivals } from '../hooks/useGlobalArrivals';

export const MainPage: React.FC = () => {
  const [selectedStation, setSelectedStation] = useState<Station | null>(null);
  const { allArrivals, isLoading } = useGlobalArrivals();

  // Identify stations that currently have non-stop transit (isSkipping: true)
  const skippingStationIds = useMemo(() => {
    return Array.from(new Set(
      allArrivals
        .filter(a => a.isSkipping)
        .map(a => a.statnId)
    ));
  }, [allArrivals]);

  const { upArrival, downArrival } = useMemo(() => {
    if (!selectedStation) return { upArrival: undefined, downArrival: undefined };
    return {
      upArrival: getFirstArrival(allArrivals, selectedStation.id, '0'),
      downArrival: getFirstArrival(allArrivals, selectedStation.id, '1')
    };
  }, [selectedStation, allArrivals]);

  return (
    <div className="min-h-screen flex flex-col bg-gray-50">
      <Header />

      <main className="flex-1 flex flex-col relative">
        {/* Search Section */}
        <div className="bg-white border-b border-gray-200 px-4 py-8 shadow-sm z-10">
          <div className="max-w-3xl mx-auto text-center mb-6">
            <h1 className="text-3xl font-extrabold text-gray-900 mb-2 tracking-tight">
              어디로 가시나요?
            </h1>
            <p className="text-gray-500">
              1호선 실시간 관제 시스템입니다.
            </p>
          </div>
          <SearchBar />
        </div>

        {/* Global Notices Area */}
        <div className="max-w-7xl mx-auto w-full px-4 mt-6">
          <ServiceNoticeBanner variant="banner" />
        </div>

        {/* Route Map Section */}
        <div className="flex-1 relative bg-gray-50">
          <div className="py-6">
            <div className="max-w-7xl mx-auto px-4">
              {/* Map header with legend and status */}
              <div className="flex flex-col sm:flex-row sm:items-center gap-3 mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-3 h-3 rounded-full bg-line1" />
                  <h2 className="text-sm font-bold text-gray-500 uppercase tracking-wider">
                    1호선 실시간 노선도 {isLoading && '(갱신 중...)'}
                  </h2>
                </div>
                <div className="flex-1 h-px bg-gray-200 hidden sm:block" />
                <div className="flex items-center gap-3 flex-wrap">
                  <UpdateStatusBadge />
                  <div className="flex items-center gap-4 text-xs text-gray-400">
                    <span className="flex items-center gap-1.5">
                      <span className="w-3 h-3 rounded-full bg-line1 border-2 border-white" />
                      일반역
                    </span>
                    {skippingStationIds.length > 0 && (
                      <span className="flex items-center gap-1.5">
                        <span className="w-3 h-3 rounded-full bg-rose-500 border-2 border-white animate-pulse" />
                        무정차 통과 중
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </div>

            <RouteMap
              stations={stations}
              selectedStation={selectedStation}
              onSelectStation={setSelectedStation}
              onDeselect={() => setSelectedStation(null)}
              skippingStationIds={skippingStationIds} />
            

            {/* Inline metadata/status */}
            <div className="max-w-7xl mx-auto px-4 mt-4">
              <ServiceNoticeBanner variant="inline" />
            </div>
          </div>

          {/* Floating Preview Card - Desktop */}
          <AnimatePresence>
            {selectedStation &&
            <div className="fixed bottom-6 right-6 z-30 hidden md:block">
                <StationPreviewCard
                station={selectedStation}
                upArrival={upArrival}
                downArrival={downArrival}
                onClose={() => setSelectedStation(null)} />
              
              </div>
            }
          </AnimatePresence>

          {/* Floating Preview Card - Mobile */}
          <AnimatePresence>
            {selectedStation &&
            <div className="fixed bottom-4 left-4 right-4 z-30 md:hidden">
                <StationPreviewCard
                station={selectedStation}
                upArrival={upArrival}
                downArrival={downArrival}
                onClose={() => setSelectedStation(null)} />
              
              </div>
            }
          </AnimatePresence>
        </div>
      </main>
    </div>);

};