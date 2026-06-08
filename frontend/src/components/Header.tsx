import React, { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Train, Activity, Clock, LogOut, LogIn, UserCircle } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
export const Header: React.FC = () => {
  const [currentTime, setCurrentTime] = useState(new Date());
  const location = useLocation();
  const navigate = useNavigate();
  const { isAuthenticated, isAdmin, user, logout } = useAuth();
  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);
  const formatTime = (date: Date) => {
    return date.toLocaleTimeString('ko-KR', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  };
  const handleLogout = () => {
    logout();
    navigate('/');
  };
  const isAdminArea = location.pathname.startsWith('/admin');
  return (
    <header className="bg-white border-b border-gray-200 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          <div className="flex items-center">
            <Link to="/" className="flex items-center gap-2 group">
              <div className="w-8 h-8 rounded-full bg-line1 flex items-center justify-center text-white group-hover:scale-105 transition-transform">
                <Train size={18} />
              </div>
              <span className="font-bold text-lg text-gray-900 tracking-tight">
                서울 지하철 1호선
              </span>
            </Link>
          </div>

          <div className="flex items-center gap-4 sm:gap-6">
            <div className="hidden sm:flex items-center gap-1.5 text-sm text-gray-500 bg-gray-50 px-3 py-1.5 rounded-full border border-gray-100">
              <Clock size={14} />
              <span className="font-medium tabular-nums">
                {formatTime(currentTime)}
              </span>
            </div>

            <nav className="flex items-center gap-3 sm:gap-4">
              <Link
                to="/"
                className={`text-sm font-medium transition-colors ${location.pathname === '/' ? 'text-line1' : 'text-gray-500 hover:text-gray-900'}`}>
                
                노선도
              </Link>

              {isAuthenticated ?
              <>
                {isAdmin &&
                  <Link
                  to="/admin"
                  className={`flex items-center gap-1 text-sm font-medium transition-colors ${isAdminArea ? 'text-line1' : 'text-gray-500 hover:text-gray-900'}`}>
                  
                    <Activity size={16} />
                    <span className="hidden sm:inline">관제 요약</span>
                  </Link>
                }
                  <div className="h-4 w-px bg-gray-200" />
                  <div className="flex items-center gap-2">
                    {user?.profileImageUrl ?
                    <img
                      src={user.profileImageUrl}
                      alt=""
                      className="w-6 h-6 rounded-full border border-gray-200" /> :
                    <UserCircle size={18} className="text-gray-400" />
                    }
                    <span className="hidden sm:inline text-xs text-gray-400">
                      {user?.name}
                    </span>
                    <button
                    onClick={handleLogout}
                    className="flex items-center gap-1 text-sm text-gray-500 hover:text-red-600 transition-colors"
                    title="로그아웃">
                    
                      <LogOut size={16} />
                    </button>
                  </div>
                </> :

              <Link
                to="/login"
                className="flex items-center gap-1 text-sm font-medium text-gray-500 hover:text-gray-900 transition-colors">
                
                  <LogIn size={16} />
                  <span className="hidden sm:inline">로그인</span>
                </Link>
              }
            </nav>
          </div>
        </div>
      </div>
    </header>);

};
