import React, { useState } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  Train,
  ShieldCheck,
  Eye,
  EyeOff,
  AlertCircle,
  Loader2 } from
'lucide-react';
import { motion } from 'framer-motion';
export const AdminLoginPage: React.FC = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from =
  (
  location.state as {
    from?: {
      pathname: string;
    };
  })?.
  from?.pathname || '/admin';
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (!username.trim() || !password.trim()) {
      setError('아이디와 비밀번호를 입력해주세요.');
      return;
    }
    setIsLoading(true);
    const success = await login(username, password);
    setIsLoading(false);
    if (success) {
      navigate(from, {
        replace: true
      });
    } else {
      setError('아이디 또는 비밀번호가 올바르지 않습니다.');
    }
  };
  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Minimal header */}
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

      {/* Login form */}
      <div className="flex-1 flex items-center justify-center px-4 py-12">
        <motion.div
          initial={{
            opacity: 0,
            y: 20
          }}
          animate={{
            opacity: 1,
            y: 0
          }}
          className="w-full max-w-md">
          
          <div className="bg-white rounded-3xl shadow-sm border border-gray-200 overflow-hidden">
            {/* Header */}
            <div className="bg-line1 px-8 py-8 text-center">
              <div className="w-14 h-14 bg-white/20 rounded-2xl flex items-center justify-center mx-auto mb-4">
                <ShieldCheck size={28} className="text-white" />
              </div>
              <h1 className="text-2xl font-bold text-white">관리자 로그인</h1>
              <p className="text-blue-200 text-sm mt-2">
                AI 이상탐지 관제 시스템에 접근하려면 인증이 필요합니다.
              </p>
            </div>

            {/* Form */}
            <form onSubmit={handleSubmit} className="px-8 py-8 space-y-5">
              {error &&
              <motion.div
                initial={{
                  opacity: 0,
                  y: -10
                }}
                animate={{
                  opacity: 1,
                  y: 0
                }}
                className="flex items-center gap-2 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl text-sm">
                
                  <AlertCircle size={16} className="shrink-0" />
                  <span>{error}</span>
                </motion.div>
              }

              <div>
                <label
                  htmlFor="username"
                  className="block text-sm font-semibold text-gray-700 mb-2">
                  
                  아이디
                </label>
                <input
                  id="username"
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="w-full px-4 py-3 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-line1 focus:border-line1 transition-all"
                  placeholder="관리자 아이디를 입력하세요"
                  autoComplete="username"
                  disabled={isLoading} />
                
              </div>

              <div>
                <label
                  htmlFor="password"
                  className="block text-sm font-semibold text-gray-700 mb-2">
                  
                  비밀번호
                </label>
                <div className="relative">
                  <input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full px-4 py-3 pr-12 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-line1 focus:border-line1 transition-all"
                    placeholder="비밀번호를 입력하세요"
                    autoComplete="current-password"
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
                    인증 중...
                  </> :

                '로그인'
                }
              </button>

              <div className="text-center pt-2">
                <p className="text-xs text-gray-400">
                  데모 계정: admin / admin1234
                </p>
              </div>
            </form>
          </div>

          <div className="text-center mt-6">
            <Link
              to="/"
              className="text-sm text-gray-500 hover:text-line1 transition-colors">
              
              ← 메인 페이지로 돌아가기
            </Link>
          </div>
        </motion.div>
      </div>
    </div>);

};