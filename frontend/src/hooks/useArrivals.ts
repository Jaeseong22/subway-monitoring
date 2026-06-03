import { useState, useEffect } from 'react';
import { ArrivalInfo } from '../types';

export const useArrivals = (stationId?: string) => {
  const [arrivals, setArrivals] = useState<ArrivalInfo[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!stationId) {
      setArrivals([]);
      return;
    }

    const fetchArrivals = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const apiUrl = (import.meta as any).env.VITE_API_URL || 'http://localhost:8080';
        const response = await fetch(`${apiUrl}/api/v1/stations/${stationId}/arrivals`);
        if (!response.ok) {
          throw new Error('Failed to fetch arrival info');
        }
        const data = await response.json();
        setArrivals(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setIsLoading(false);
      }
    };

    fetchArrivals();
    
    // Set up polling every 60 seconds (Backend interval is 1-2 minutes)
    const intervalId = setInterval(fetchArrivals, 60000);
    return () => clearInterval(intervalId);
  }, [stationId]);

  return { arrivals, isLoading, error };
};
