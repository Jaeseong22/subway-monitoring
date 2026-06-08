import React, { useCallback, useContext, useState, createContext } from 'react';

export interface AuthUser {
  id: number;
  name: string;
  email: string;
  role: 'USER' | 'ADMIN' | string;
  provider: 'LOCAL' | 'GOOGLE' | string;
  profileImageUrl?: string | null;
}

interface AuthState {
  isAuthenticated: boolean;
  token: string | null;
  user: AuthUser | null;
}

interface AuthContextType extends AuthState {
  isAdmin: boolean;
  login: (email: string, password: string) => Promise<boolean>;
  register: (name: string, email: string, password: string) => Promise<boolean>;
  loginWithGoogle: (idToken: string) => Promise<boolean>;
  logout: () => void;
  error: string;
  clearError: () => void;
}

interface AuthResponse {
  token: string;
  user: AuthUser;
}

const STORAGE_KEY = 'subway_auth';
const AuthContext = createContext<AuthContextType | null>(null);

const apiUrl = () => (import.meta as any).env.VITE_API_URL || 'http://localhost:8080';

const loadInitialState = (): AuthState => {
  const stored = sessionStorage.getItem(STORAGE_KEY);
  if (!stored) {
    return { isAuthenticated: false, token: null, user: null };
  }

  try {
    const parsed = JSON.parse(stored) as AuthState;
    return {
      isAuthenticated: Boolean(parsed.token && parsed.user),
      token: parsed.token,
      user: parsed.user
    };
  } catch {
    sessionStorage.removeItem(STORAGE_KEY);
    return { isAuthenticated: false, token: null, user: null };
  }
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [authState, setAuthState] = useState<AuthState>(loadInitialState);
  const [error, setError] = useState('');

  const saveSession = useCallback((response: AuthResponse) => {
    const nextState: AuthState = {
      isAuthenticated: true,
      token: response.token,
      user: response.user
    };
    setAuthState(nextState);
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(nextState));
  }, []);

  const requestAuth = useCallback(
    async (path: string, payload: Record<string, string>): Promise<boolean> => {
      setError('');
      try {
        const response = await fetch(`${apiUrl()}${path}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        if (!response.ok) {
          const body = await response.json().catch(() => ({}));
          setError(body.message || '인증 요청을 처리하지 못했습니다.');
          return false;
        }

        saveSession(await response.json());
        return true;
      } catch {
        setError('서버에 연결할 수 없습니다.');
        return false;
      }
    },
    [saveSession]
  );

  const login = useCallback(
    (email: string, password: string) =>
      requestAuth('/api/v1/auth/login', { email, password }),
    [requestAuth]
  );

  const register = useCallback(
    (name: string, email: string, password: string) =>
      requestAuth('/api/v1/auth/register', { name, email, password }),
    [requestAuth]
  );

  const loginWithGoogle = useCallback(
    (idToken: string) =>
      requestAuth('/api/v1/auth/google', { idToken }),
    [requestAuth]
  );

  const logout = useCallback(() => {
    setAuthState({ isAuthenticated: false, token: null, user: null });
    sessionStorage.removeItem(STORAGE_KEY);
  }, []);

  const clearError = useCallback(() => setError(''), []);

  return (
    <AuthContext.Provider
      value={{
        ...authState,
        isAdmin: authState.user?.role === 'ADMIN',
        login,
        register,
        loginWithGoogle,
        logout,
        error,
        clearError
      }}>
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
