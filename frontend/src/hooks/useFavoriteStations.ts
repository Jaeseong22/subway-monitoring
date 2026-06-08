import { useCallback, useEffect, useMemo, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { FavoriteStation } from '../types';

const apiUrl = () => (import.meta as any).env.VITE_API_URL || 'http://localhost:8080';

export const useFavoriteStations = () => {
  const { token, isAuthenticated } = useAuth();
  const [favorites, setFavorites] = useState<FavoriteStation[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const headers = useMemo(() => ({
    Authorization: `Bearer ${token}`
  }), [token]);

  const refresh = useCallback(async () => {
    if (!token) {
      setFavorites([]);
      return;
    }
    setIsLoading(true);
    try {
      const response = await fetch(`${apiUrl()}/api/v1/users/me/favorites`, { headers });
      if (response.ok) {
        setFavorites(await response.json());
      }
    } finally {
      setIsLoading(false);
    }
  }, [headers, token]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const isFavorite = useCallback(
    (stationId: string) => favorites.some((favorite) => favorite.stationId === stationId),
    [favorites]
  );

  const toggleFavorite = useCallback(async (stationId: string) => {
    if (!token || !isAuthenticated) {
      return;
    }
    const method = isFavorite(stationId) ? 'DELETE' : 'POST';
    const response = await fetch(`${apiUrl()}/api/v1/users/me/favorites/${stationId}`, {
      method,
      headers
    });
    if (response.ok) {
      await refresh();
    }
  }, [headers, isAuthenticated, isFavorite, refresh, token]);

  return { favorites, isLoading, isFavorite, toggleFavorite, refresh };
};

