import { useCallback, useEffect, useState } from 'react';
import { Station } from '../types';

const apiBase = () =>
  (import.meta as any).env.VITE_API_URL || 'http://localhost:8080';

/**
 * 역 마스터 데이터를 백엔드에서 가져온다.
 *
 * 이전에는 프론트엔드가 하드코딩 목업(data/mockData.ts)을 사용해 DB와 이원화되어
 * 있었다. 역 정보가 바뀌면 두 곳을 모두 고쳐야 했고 실제로 서로 다른 목록을
 * 보여주고 있었다. 이제 백엔드 DB가 단일 원본이다.
 *
 * 역 목록은 거의 변하지 않으므로 모듈 수준에서 한 번만 받아 공유한다.
 */
let cache: Station[] | null = null;
let inflight: Promise<Station[]> | null = null;

const loadStations = (): Promise<Station[]> => {
  if (cache) return Promise.resolve(cache);
  if (inflight) return inflight;

  inflight = fetch(`${apiBase()}/api/v1/stations`).
  then((res) => {
    if (!res.ok) throw new Error(`역 정보를 불러오지 못했습니다 (HTTP ${res.status})`);
    return res.json();
  }).
  then((data: Station[]) => {
    cache = data;
    return data;
  }).
  finally(() => {
    inflight = null;
  });

  return inflight;
};

export const useStations = () => {
  const [stations, setStations] = useState<Station[]>(cache ?? []);
  const [isLoading, setIsLoading] = useState<boolean>(cache === null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    cache = null;
    setIsLoading(true);
    return loadStations().
    then(setStations).
    catch((err: unknown) =>
    setError(err instanceof Error ? err.message : '역 정보를 불러오지 못했습니다.')
    ).
    finally(() => setIsLoading(false));
  }, []);

  useEffect(() => {
    let active = true;
    if (cache) {
      setStations(cache);
      setIsLoading(false);
      return;
    }
    loadStations().
    then((data) => {
      if (active) {
        setStations(data);
        setError(null);
      }
    }).
    catch((err: unknown) => {
      if (active) {
        setError(err instanceof Error ? err.message : '역 정보를 불러오지 못했습니다.');
      }
    }).
    finally(() => {
      if (active) setIsLoading(false);
    });
    return () => {
      active = false;
    };
  }, []);

  return { stations, isLoading, error, refresh };
};
