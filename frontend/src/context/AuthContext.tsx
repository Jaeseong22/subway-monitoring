import React, { useCallback, useState, createContext, useContext } from 'react';
interface AuthState {
  isAuthenticated: boolean;
  user: {
    username: string;
    role: string;
  } | null;
}
interface AuthContextType extends AuthState {
  login: (username: string, password: string) => Promise<boolean>;
  logout: () => void;
}
const AuthContext = createContext<AuthContextType | null>(null);
// Mock credentials - replace with real API later
const MOCK_ADMIN = {
  username: 'admin',
  password: 'admin1234'
};
export const AuthProvider: React.FC<{
  children: React.ReactNode;
}> = ({ children }) => {
  const [authState, setAuthState] = useState<AuthState>(() => {
    const stored = sessionStorage.getItem('admin_auth');
    if (stored) {
      try {
        return JSON.parse(stored);
      } catch {
        return {
          isAuthenticated: false,
          user: null
        };
      }
    }
    return {
      isAuthenticated: false,
      user: null
    };
  });
  const login = useCallback(
    async (username: string, password: string): Promise<boolean> => {
      // Simulate API call delay
      await new Promise((resolve) => setTimeout(resolve, 600));
      if (
      username === MOCK_ADMIN.username &&
      password === MOCK_ADMIN.password)
      {
        const newState: AuthState = {
          isAuthenticated: true,
          user: {
            username,
            role: 'admin'
          }
        };
        setAuthState(newState);
        sessionStorage.setItem('admin_auth', JSON.stringify(newState));
        return true;
      }
      return false;
    },
    []
  );
  const logout = useCallback(() => {
    setAuthState({
      isAuthenticated: false,
      user: null
    });
    sessionStorage.removeItem('admin_auth');
  }, []);
  return (
    <AuthContext.Provider
      value={{
        ...authState,
        login,
        logout
      }}>
      
      {children}
    </AuthContext.Provider>);

};
export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}