import { useState, useEffect } from 'react';
import { ArrivalInfo } from '../types';
import { API_BASE } from '../utils/api';

export const useGlobalArrivals = () => {
  const [allArrivals, setAllArrivals] = useState<ArrivalInfo[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const fetchAllArrivals = async () => {
    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/v1/stations/arrivals/all`);
      if (!response.ok) {
        throw new Error('Failed to fetch global arrival info');
      }
      const data = await response.json();
      setAllArrivals(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchAllArrivals();
    // Poll every 30 seconds (Matching backend peak interval)
    const intervalId = setInterval(fetchAllArrivals, 30000);
    return () => clearInterval(intervalId);
  }, []);

  return { allArrivals, isLoading, error, refresh: fetchAllArrivals };
};
