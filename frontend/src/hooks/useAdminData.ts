import { useState, useEffect } from 'react';
import { Anomaly, AIInsight, AdminSummary } from '../types';

export const useAdminData = () => {
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [insights, setInsights] = useState<AIInsight[]>([]);
  const [summary, setSummary] = useState<AdminSummary | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    const fetchAdminData = async () => {
      setIsLoading(true);
      try {
        const apiUrl = (import.meta as any).env.VITE_API_URL || 'http://localhost:8080';
        const [anomaliesRes, insightsRes, summaryRes] = await Promise.all([
          fetch(`${apiUrl}/api/v1/admin/anomalies`),
          fetch(`${apiUrl}/api/v1/admin/insights`),
          fetch(`${apiUrl}/api/v1/admin/summary`)
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
  }, []);

  return { anomalies, insights, summary, isLoading };
};
