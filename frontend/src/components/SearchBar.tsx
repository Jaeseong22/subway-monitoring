import React, { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, MapPin } from 'lucide-react';
import { stations } from '../data/mockData';
import { Station } from '../types';
import { motion, AnimatePresence } from 'framer-motion';
export const SearchBar: React.FC = () => {
  const [query, setQuery] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const [results, setResults] = useState<Station[]>([]);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  useEffect(() => {
    if (query.trim() === '') {
      setResults([]);
      return;
    }
    const filtered = stations.
    filter(
      (s) =>
      s.name.includes(query) ||
      s.nameEn.toLowerCase().includes(query.toLowerCase())
    ).
    slice(0, 5);
    setResults(filtered);
  }, [query]);
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
      wrapperRef.current &&
      !wrapperRef.current.contains(event.target as Node))
      {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);
  const handleSelect = (stationId: string) => {
    setIsOpen(false);
    setQuery('');
    navigate(`/station/${stationId}`);
  };
  return (
    <div ref={wrapperRef} className="relative w-full max-w-xl mx-auto">
      <div className="relative">
        <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
          <Search className="h-5 w-5 text-gray-400" />
        </div>
        <input
          type="text"
          className="block w-full pl-11 pr-4 py-3.5 border border-gray-200 rounded-2xl leading-5 bg-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-line1 focus:border-line1 sm:text-sm transition-all shadow-sm"
          placeholder="역 이름을 검색하세요 (예: 서울역, 청량리)"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setIsOpen(true);
          }}
          onFocus={() => setIsOpen(true)} />
        
      </div>

      <AnimatePresence>
        {isOpen && query &&
        <motion.div
          initial={{
            opacity: 0,
            y: -10
          }}
          animate={{
            opacity: 1,
            y: 0
          }}
          exit={{
            opacity: 0,
            y: -10
          }}
          transition={{
            duration: 0.15
          }}
          className="absolute z-10 mt-2 w-full bg-white rounded-xl shadow-lg border border-gray-100 overflow-hidden">
          
            {results.length > 0 ?
          <ul className="max-h-60 overflow-auto py-1">
                {results.map((station) =>
            <li
              key={station.id}
              className="px-4 py-3 hover:bg-gray-50 cursor-pointer flex items-center gap-3 transition-colors"
              onClick={() => handleSelect(station.id)}>
              
                    <div className="w-8 h-8 rounded-full bg-blue-50 flex items-center justify-center flex-shrink-0">
                      <MapPin size={16} className="text-line1" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-gray-900">
                          {station.name}
                        </span>
                        {station.hasTransfer &&
                  <span className="text-[10px] px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded-sm font-medium">
                            환승
                          </span>
                  }
                      </div>
                      <span className="text-xs text-gray-500">
                        {station.nameEn}
                      </span>
                    </div>
                  </li>
            )}
              </ul> :

          <div className="px-4 py-8 text-center text-gray-500 text-sm">
                검색 결과가 없습니다.
              </div>
          }
          </motion.div>
        }
      </AnimatePresence>
    </div>);

};