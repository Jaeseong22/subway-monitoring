import { useState, useEffect } from 'react';
import { Anomaly, AIInsight, AdminSummary } from '../types';
import { useAuth } from '../context/AuthContext';

export const useAdminData = () => {
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [insights, setInsights] = useState<AIInsight[]>([]);
  const [summary, setSummary] = useState<AdminSummary | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const { token } = useAuth();

  useEffect(() => {
    const fetchAdminData = async () => {
      if (!token) {
        setIsLoading(false);
        return;
      }
      setIsLoading(true);
      try {
        const apiUrl = (import.meta as any).env.VITE_API_URL || 'http://localhost:8080';
        const options = {
          headers: {
            Authorization: `Bearer ${token}`
          }
        };
        const [anomaliesRes, insightsRes, summaryRes] = await Promise.all([
          fetch(`${apiUrl}/api/v1/admin/anomalies`, options),
          fetch(`${apiUrl}/api/v1/admin/insights`, options),
          fetch(`${apiUrl}/api/v1/admin/summary`, options)
        ]);
        
        if (anomaliesRes.ok) setAnomalies(await anomaliesRes.json());
        if (insightsRes.ok) setInsights(await insightsRes.json());
        if (summaryRes.ok) setSummary(await summaryRes.json());
        
      } catch (err) {
        console.error('Failed to fetch admin data', err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchAdminData();
  }, [token]);

  return { anomalies, insights, summary, isLoading };
};
