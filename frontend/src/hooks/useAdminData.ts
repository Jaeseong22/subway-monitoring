import { useState, useEffect } from 'react';
import { Anomaly, AIInsight, AdminSummary, Diagnosis, Verification } from '../types';
import { useAuth } from '../context/AuthContext';
import { API_BASE } from '../utils/api';

export const useAdminData = () => {
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [insights, setInsights] = useState<AIInsight[]>([]);
  const [summary, setSummary] = useState<AdminSummary | null>(null);
  const [diagnosis, setDiagnosis] = useState<Diagnosis | null>(null);
  const [verification, setVerification] = useState<Verification | null>(null);
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
        const options = {
          headers: {
            Authorization: `Bearer ${token}`
          }
        };
        const [anomaliesRes, insightsRes, summaryRes, diagnosisRes, verificationRes] =
          await Promise.all([
            fetch(`${API_BASE}/api/v1/admin/anomalies`, options),
            fetch(`${API_BASE}/api/v1/admin/insights`, options),
            fetch(`${API_BASE}/api/v1/admin/summary`, options),
            fetch(`${API_BASE}/api/v1/admin/diagnosis`, options),
            fetch(`${API_BASE}/api/v1/admin/verification`, options)
          ]);

        if (anomaliesRes.ok) setAnomalies(await anomaliesRes.json());
        if (insightsRes.ok) setInsights(await insightsRes.json());
        if (summaryRes.ok) setSummary(await summaryRes.json());
        if (diagnosisRes.ok) setDiagnosis(await diagnosisRes.json());
        if (verificationRes.ok) setVerification(await verificationRes.json());

      } catch (err) {
        console.error('Failed to fetch admin data', err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchAdminData();
  }, [token]);

  return { anomalies, insights, summary, diagnosis, verification, isLoading };
};
