import { useCallback, useEffect, useMemo, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { ArrivalAlert } from '../types';

const apiUrl = () => (import.meta as any).env.VITE_API_URL || 'http://localhost:8080';

export const useArrivalAlerts = () => {
  const { token } = useAuth();
  const [alerts, setAlerts] = useState<ArrivalAlert[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const headers = useMemo(() => ({
    Authorization: `Bearer ${token}`
  }), [token]);

  const refresh = useCallback(async () => {
    if (!token) {
      setAlerts([]);
      return;
    }
    setIsLoading(true);
    try {
      const response = await fetch(`${apiUrl()}/api/v1/users/me/arrival-alerts`, { headers });
      if (response.ok) {
        setAlerts(await response.json());
      }
    } finally {
      setIsLoading(false);
    }
  }, [headers, token]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { alerts, isLoading, refresh };
};

