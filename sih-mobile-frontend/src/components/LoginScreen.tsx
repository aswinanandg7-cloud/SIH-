import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import './LoginScreen.css';

export const LoginScreen: React.FC = () => {
  const {
    login,
    isLoading,
    authError,
    clearError,
    demoLogin,
  } = useAuth();

  const [username, setUsername] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [showPassword, setShowPassword] = useState<boolean>(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) return;
    await login(username, password);
  };

  return (
    <div className="login-wrapper">
      <div className="login-bg-glow"></div>
      
      <div className="login-card">
        <div className="brand-header">
          <div className="emblem-container">
            <svg className="ashoka-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
              <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" />
            </svg>
          </div>
          <span className="gov-tag">Government Agriculture Portal</span>
          <h1 className="app-title">Procurement Officer Login</h1>
        </div>

        {authError && (
          <div className="auth-error-banner">
            <div className="error-icon">⚠️</div>
            <div className="error-text">{authError}</div>
            <button type="button" className="close-error" onClick={clearError}>×</button>
          </div>
        )}

        <form onSubmit={handleSubmit} className="login-form">
          <div className="form-group">
            <label htmlFor="username">Username / Official ID</label>
            <div className="input-input-wrapper">
              <span className="input-icon">👤</span>
              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter username"
                required
                autoComplete="username"
              />
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <div className="input-input-wrapper">
              <span className="input-icon">🔒</span>
              <input
                id="password"
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter password"
                required
                autoComplete="current-password"
              />
              <button
                type="button"
                className="toggle-password-btn"
                onClick={() => setShowPassword(!showPassword)}
                aria-label="Toggle password visibility"
              >
                {showPassword ? (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                    <line x1="1" y1="1" x2="23" y2="23" />
                  </svg>
                ) : (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                    <circle cx="12" cy="12" r="3" />
                  </svg>
                )}
              </button>
            </div>
          </div>

          <button
            type="submit"
            className="login-submit-btn"
            disabled={isLoading || !username.trim() || !password.trim()}
          >
            {isLoading ? (
              <span className="btn-spinner-container">
                <span className="spinner"></span> Logging in...
              </span>
            ) : (
              <span>Login</span>
            )}
          </button>
        </form>

        <div className="demo-section">
          <span className="demo-divider-text">Quick Preview / Testing Actions</span>
          <div className="demo-buttons">
            <button
              type="button"
              className="demo-btn officer-demo"
              onClick={() => demoLogin('govt-agri-officer')}
            >
              ✅ Test as Officer (govt-agri-officer)
            </button>
            <button
              type="button"
              className="demo-btn clerk-demo"
              onClick={() => demoLogin('govt-agri-clerk')}
            >
              🎟️ Test as Clerk (govt-agri-clerk)
            </button>
            <button
              type="button"
              className="demo-btn user-demo"
              onClick={() => demoLogin('general-user')}
            >
              🚫 Test non-Officer/Clerk (Missing Role)
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
