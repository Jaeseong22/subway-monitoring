import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  AlertCircle,
  Eye,
  EyeOff,
  Loader2,
  LogIn,
  ShieldCheck,
  Train,
  UserPlus
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: {
            client_id: string;
            callback: (response: { credential?: string }) => void;
          }) => void;
          renderButton: (
            element: HTMLElement,
            options: {
              theme: 'outline' | 'filled_blue' | 'filled_black';
              size: 'large' | 'medium' | 'small';
              width?: number;
              text?: 'signin_with' | 'signup_with' | 'continue_with';
            }
          ) => void;
        };
      };
    };
  }
}

type AuthMode = 'login' | 'register';

export const AdminLoginPage: React.FC = () => {
  const [mode, setMode] = useState<AuthMode>('login');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [googleReady, setGoogleReady] = useState(false);
  const googleButtonRef = useRef<HTMLDivElement | null>(null);

  const { login, register, loginWithGoogle, error, clearError } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const googleClientId = (import.meta as any).env.VITE_GOOGLE_CLIENT_ID || '';
  const from = useMemo(() => {
    const state = location.state as { from?: { pathname: string } } | null;
    return state?.from?.pathname || '/';
  }, [location.state]);

  useEffect(() => {
    clearError();
  }, [mode, clearError]);

  useEffect(() => {
    if (!googleClientId || googleReady) {
      return;
    }

    const existingScript = document.querySelector<HTMLScriptElement>(
      'script[src="https://accounts.google.com/gsi/client"]'
    );

    const initialize = () => setGoogleReady(true);
    if (existingScript) {
      initialize();
      return;
    }

    const script = document.createElement('script');
    script.src = 'https://accounts.google.com/gsi/client';
    script.async = true;
    script.defer = true;
    script.onload = initialize;
    document.body.appendChild(script);
  }, [googleClientId, googleReady]);

  useEffect(() => {
    if (!googleReady || !googleClientId || !window.google || !googleButtonRef.current) {
      return;
    }

    googleButtonRef.current.innerHTML = '';
    window.google.accounts.id.initialize({
      client_id: googleClientId,
      callback: async (response) => {
        if (!response.credential) {
          return;
        }
        setIsLoading(true);
        const success = await loginWithGoogle(response.credential);
        setIsLoading(false);
        if (success) {
          navigateAfterLogin(from);
        }
      }
    });
    window.google.accounts.id.renderButton(googleButtonRef.current, {
      theme: 'outline',
      size: 'large',
      width: 352,
      text: 'continue_with'
    });
  }, [from, googleClientId, googleReady, loginWithGoogle]);

  const navigateAfterLogin = (nextPath: string) => {
    navigate(nextPath, { replace: true });
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    clearError();

    if (!email.trim() || !password.trim() || (mode === 'register' && !name.trim())) {
      return;
    }

    setIsLoading(true);
    const success =
      mode === 'login'
        ? await login(email, password)
        : await register(name, email, password);
    setIsLoading(false);

    if (success) {
      navigateAfterLogin(from);
    }
  };

  const switchMode = (nextMode: AuthMode) => {
    setMode(nextMode);
    setName('');
    setPassword('');
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center h-16">
            <Link to="/" className="flex items-center gap-2 group">
              <div className="w-8 h-8 rounded-full bg-line1 flex items-center justify-center text-white group-hover:scale-105 transition-transform">
                <Train size={18} />
              </div>
              <span className="font-bold text-lg text-gray-900 tracking-tight">
                서울 지하철 1호선
              </span>
            </Link>
          </div>
        </div>
      </header>

      <div className="flex-1 flex items-center justify-center px-4 py-10">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="w-full max-w-md">
          <div className="bg-white rounded-2xl shadow-sm border border-gray-200 overflow-hidden">
            <div className="bg-line1 px-8 py-8 text-center">
              <div className="w-14 h-14 bg-white/20 rounded-2xl flex items-center justify-center mx-auto mb-4">
                {mode === 'login' ?
                  <LogIn size={28} className="text-white" /> :
                  <UserPlus size={28} className="text-white" />
                }
              </div>
              <h1 className="text-2xl font-bold text-white">
                {mode === 'login' ? '로그인' : '회원가입'}
              </h1>
              <p className="text-blue-200 text-sm mt-2">
                로그인 후 관리자 권한 계정만 관제 요약에 접근할 수 있습니다.
              </p>
            </div>

            <div className="px-8 pt-6">
              <div className="grid grid-cols-2 rounded-xl border border-gray-200 bg-gray-50 p-1">
                <button
                  type="button"
                  onClick={() => switchMode('login')}
                  className={`h-10 rounded-lg text-sm font-semibold transition-colors ${
                    mode === 'login'
                      ? 'bg-white text-line1 shadow-sm'
                      : 'text-gray-500 hover:text-gray-800'
                  }`}>
                  로그인
                </button>
                <button
                  type="button"
                  onClick={() => switchMode('register')}
                  className={`h-10 rounded-lg text-sm font-semibold transition-colors ${
                    mode === 'register'
                      ? 'bg-white text-line1 shadow-sm'
                      : 'text-gray-500 hover:text-gray-800'
                  }`}>
                  회원가입
                </button>
              </div>
            </div>

            <form onSubmit={handleSubmit} className="px-8 py-6 space-y-4">
              {error &&
                <motion.div
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex items-center gap-2 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl text-sm">
                  <AlertCircle size={16} className="shrink-0" />
                  <span>{error}</span>
                </motion.div>
              }

              {mode === 'register' &&
                <div>
                  <label htmlFor="name" className="block text-sm font-semibold text-gray-700 mb-2">
                    이름
                  </label>
                  <input
                    id="name"
                    type="text"
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                    className="w-full px-4 py-3 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-line1 focus:border-line1 transition-all"
                    placeholder="이름을 입력하세요"
                    autoComplete="name"
                    disabled={isLoading} />
                </div>
              }

              <div>
                <label htmlFor="email" className="block text-sm font-semibold text-gray-700 mb-2">
                  이메일
                </label>
                <input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  className="w-full px-4 py-3 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-line1 focus:border-line1 transition-all"
                  placeholder="email@example.com"
                  autoComplete="email"
                  disabled={isLoading} />
              </div>

              <div>
                <label htmlFor="password" className="block text-sm font-semibold text-gray-700 mb-2">
                  비밀번호
                </label>
                <div className="relative">
                  <input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    className="w-full px-4 py-3 pr-12 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-line1 focus:border-line1 transition-all"
                    placeholder="8자 이상 입력하세요"
                    autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                    disabled={isLoading} />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
                    tabIndex={-1}>
                    {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
              </div>

              <button
                type="submit"
                disabled={isLoading}
                className="w-full py-3 bg-line1 hover:bg-line1/90 text-white rounded-xl font-semibold text-sm transition-colors disabled:opacity-60 disabled:cursor-not-allowed flex items-center justify-center gap-2">
                {isLoading ?
                  <>
                    <Loader2 size={18} className="animate-spin" />
                    처리 중...
                  </> :
                  mode === 'login' ? '로그인' : '회원가입'
                }
              </button>

              <div className="relative py-2">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-gray-200" />
                </div>
                <div className="relative flex justify-center">
                  <span className="bg-white px-3 text-xs text-gray-400">또는</span>
                </div>
              </div>

              {googleClientId ?
                <div className="flex justify-center min-h-[44px]">
                  <div ref={googleButtonRef} />
                </div> :
                <div className="rounded-xl border border-dashed border-gray-200 bg-gray-50 px-4 py-3 text-center text-xs text-gray-500">
                  Google 로그인은 `VITE_GOOGLE_CLIENT_ID` 설정 후 사용할 수 있습니다.
                </div>
              }

              <div className="rounded-xl bg-blue-50 border border-blue-100 px-4 py-3 text-xs text-blue-700 flex gap-2">
                <ShieldCheck size={15} className="shrink-0 mt-0.5" />
                <span>
                  관리자 권한이 있는 계정으로 로그인하면 관제 요약 버튼이 표시됩니다.
                </span>
              </div>
            </form>
          </div>

          <div className="text-center mt-6">
            <Link to="/" className="text-sm text-gray-500 hover:text-line1 transition-colors">
              메인 페이지로 돌아가기
            </Link>
          </div>
        </motion.div>
      </div>
    </div>
  );
};
