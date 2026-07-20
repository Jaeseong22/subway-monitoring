import { useState, useEffect } from 'react';
import { ArrivalInfo } from '../types';
import { useAuth } from '../context/AuthContext';
import { API_BASE } from '../utils/api';

export const useArrivals = (stationId?: string) => {
  const [arrivals, setArrivals] = useState<ArrivalInfo[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const { token } = useAuth();

  useEffect(() => {
    if (!stationId) {
      setArrivals([]);
      return;
    }

    const fetchArrivals = async () => {
      setIsLoading(true);
        setError(null);
        try {
        const response = await fetch(`${API_BASE}/api/v1/stations/${stationId}/arrivals`, {
          headers: token ? { Authorization: `Bearer ${token}` } : undefined
        });
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
  }, [stationId, token]);

  return { arrivals, isLoading, error };
};
