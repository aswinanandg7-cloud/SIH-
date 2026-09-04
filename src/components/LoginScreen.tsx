import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import './LoginScreen.css';

const LoginScreen: React.FC = () => {
  const { login, demoLogin, isLoading, authError, clearError } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  useEffect(() => {
    return () => {
      clearError();
    };
  }, [clearError]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username || !password) return;
    await login(username, password);
  };

  return (
    <div className="login-wrapper">
      <div className="login-bg-glow" />
      <div className="login-card">
        
        <div className="brand-header">
          <div className="emblem-container">
             <div className="ashoka-icon" style={{fontSize: "1.2rem"}}>🌾</div>
          </div>
          <span className="gov-tag">GOVERNMENT OF INDIA</span>
          <h1 className="app-title">AgroProcure Unified</h1>
          <p className="app-subtitle">Official Procurement Management Portal</p>
        </div>

        {authError && (
          <div className="auth-error-banner">
            <span className="error-icon">⚠️</span>
            <span className="error-text">{authError}</span>
            <button className="close-error" onClick={clearError}>&times;</button>
          </div>
        )}

        <form className="login-form" onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="username">Email or Employee ID</label>
            <div className="input-input-wrapper">
              <span className="input-icon">👤</span>
              <input
                type="text"
                id="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="e.g. officer.rajesh@agri.gov.in"
                required
                disabled={isLoading}
              />
            </div>
          </div>
          
          <div className="form-group">
            <label htmlFor="password">Password</label>
            <div className="input-input-wrapper">
              <span className="input-icon">🔒</span>
              <input
                type={showPassword ? "text" : "password"}
                id="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                disabled={isLoading}
              />
              <button 
                type="button" 
                className="toggle-password-btn" 
                onClick={() => setShowPassword(!showPassword)}
                tabIndex={-1}
              >
                {showPassword ? "👁️" : "👁️‍🗨️"}
              </button>
            </div>
          </div>

          <button 
            type="submit" 
            className="login-submit-btn" 
            disabled={isLoading || !username || !password}
          >
            {isLoading ? (
               <div className="btn-spinner-container">
                  <div className="spinner"></div>
                  Authenticating...
               </div>
            ) : 'Secure Login'}
          </button>
        </form>

        <div className="demo-section">
          <span className="demo-divider-text">Quick Access (Demo)</span>
          <div className="demo-buttons">
            <button 
              type="button" 
              className="demo-btn officer-demo" 
              onClick={() => demoLogin('govt-agri-officer')}
              disabled={isLoading}
            >
              🧑‍💼 Login as District Agri Officer
            </button>
            <button 
              type="button" 
              className="demo-btn clerk-demo" 
              onClick={() => demoLogin('govt-agri-clerk')}
              disabled={isLoading}
            >
              🧑‍💻 Login as Verification Clerk
            </button>
            <button 
              type="button" 
              className="demo-btn user-demo" 
              onClick={() => demoLogin('general-user')}
              disabled={isLoading}
            >
              🚜 Login as Farmer (Test Mode)
            </button>
          </div>
        </div>
        
      </div>
    </div>
  );
};

export default LoginScreen;
