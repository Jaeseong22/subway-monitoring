import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { ProtectedRoute } from './components/ProtectedRoute';
import { MainPage } from './pages/MainPage';
import { StationDetailPage } from './pages/StationDetailPage';
import { AdminPage } from './pages/AdminPage';
import { AdminLoginPage } from './pages/AdminLoginPage';
export function App() {
  return (
    <Router>
      <AuthProvider>
        <div className="min-h-screen bg-gray-50 text-gray-900 font-sans">
          <Routes>
            <Route path="/" element={<MainPage />} />
            <Route path="/station/:id" element={<StationDetailPage />} />
            <Route path="/admin/login" element={<AdminLoginPage />} />
            <Route
              path="/admin"
              element={
              <ProtectedRoute>
                  <AdminPage />
                </ProtectedRoute>
              } />
            
          </Routes>
        </div>
      </AuthProvider>
    </Router>);

}