import { useCallback, useEffect, useRef, useState } from 'react';
import { RemediationAction } from '../types';
import { useAuth } from '../context/AuthContext';

const POLL_INTERVAL_MS = 15000;

const apiBase = () =>
  (import.meta as any).env.VITE_API_URL || 'http://localhost:8080';

/**
 * AI가 제안한 자동 대응 조치를 조회하고 승인/거부한다.
 *
 * 조치는 워커가 비동기로 실행하므로(APPROVED → EXECUTING → EXECUTED → 검증),
 * 상태가 화면에서 저절로 진행되도록 주기적으로 다시 불러온다.
 */
export const useRemediation = () => {
  const [actions, setActions] = useState<RemediationAction[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const { token } = useAuth();
  // 요청이 겹칠 때 오래된 응답이 최신 상태를 덮어쓰지 않도록 한다.
  const requestSeq = useRef(0);

  const fetchActions = useCallback(async () => {
    if (!token) {
      setActions([]);
      setIsLoading(false);
      return;
    }
    const seq = ++requestSeq.current;
    try {
      const res = await fetch(`${apiBase()}/api/v1/admin/remediation`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (!res.ok) {
        throw new Error(`조치 목록을 불러오지 못했습니다 (HTTP ${res.status})`);
      }
      const data: RemediationAction[] = await res.json();
      if (seq === requestSeq.current) {
        setActions(data);
        setError(null);
      }
    } catch (err) {
      if (seq === requestSeq.current) {
        setError(err instanceof Error ? err.message : '조치 목록을 불러오지 못했습니다.');
      }
    } finally {
      if (seq === requestSeq.current) setIsLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchActions();
    if (!token) return;
    const timer = window.setInterval(fetchActions, POLL_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [fetchActions, token]);

  const decide = useCallback(
    async (actionId: string, decision: 'approve' | 'reject') => {
      if (!token) return;
      setPendingId(actionId);
      setError(null);
      try {
        const res = await fetch(
          `${apiBase()}/api/v1/admin/remediation/${actionId}/${decision}`,
          { method: 'POST', headers: { Authorization: `Bearer ${token}` } }
        );
        if (res.status === 409) {
          // 다른 관리자가 먼저 처리했거나 이미 실행된 조치다.
          setError('이미 처리된 조치입니다. 최신 상태로 갱신합니다.');
          await fetchActions();
          return;
        }
        if (!res.ok) {
          throw new Error(`처리에 실패했습니다 (HTTP ${res.status})`);
        }
        const updated: RemediationAction = await res.json();
        setActions((prev) =>
          prev.map((item) => (item.id === updated.id ? updated : item))
        );
      } catch (err) {
        setError(err instanceof Error ? err.message : '처리에 실패했습니다.');
      } finally {
        setPendingId(null);
      }
    },
    [fetchActions, token]
  );

  return {
    actions,
    isLoading,
    error,
    pendingId,
    approve: (id: string) => decide(id, 'approve'),
    reject: (id: string) => decide(id, 'reject'),
    refresh: fetchActions
  };
};
