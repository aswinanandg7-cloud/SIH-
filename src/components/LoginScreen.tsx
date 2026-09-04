import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import './LoginScreen.css';

const LoginScreen: React.FC = () => {
  const { login, demoLogin, isLoading, authError, clearError } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showConfig, setShowConfig] = useState(false);

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
    <div className="login-container">
      <div className="login-card">
        <div className="login-header">
          <div className="logo-placeholder">🌾</div>
          <h1>AgroProcure Portal</h1>
          <p>Government Agricultural Procurement System</p>
        </div>

        {authError && (
          <div className="error-banner">
            <span className="error-icon">⚠️</span>
            <span className="error-text">{authError}</span>
            <button className="error-close" onClick={clearError}>&times;</button>
          </div>
        )}

        <form className="login-form" onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="username">Email or Username</label>
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
          
          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              type="password"
              id="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              disabled={isLoading}
            />
          </div>

          <button 
            type="submit" 
            className={`btn-primary login-btn ${isLoading ? 'loading' : ''}`}
            disabled={isLoading || !username || !password}
          >
            {isLoading ? 'Authenticating...' : 'Sign In with Supabase'}
          </button>
        </form>

        <div className="divider">
          <span>OR</span>
        </div>

        <div className="demo-accounts">
          <p>Quick Access (Demo)</p>
          <button 
            type="button" 
            className="btn-outline demo-btn"
            onClick={() => demoLogin('govt-agri-officer')}
            disabled={isLoading}
          >
            🧑‍💼 Login as Agri Officer
          </button>
          <button 
            type="button" 
            className="btn-outline demo-btn"
            onClick={() => demoLogin('govt-agri-clerk')}
            disabled={isLoading}
          >
            🧑‍💻 Login as Auth Clerk
          </button>
        </div>
        
        <div className="config-footer">
          <button 
            type="button"
            className="toggle-config-btn"
            onClick={() => setShowConfig(!showConfig)}
          >
            {showConfig ? 'Hide Info' : 'Show Info'}
          </button>
          
          {showConfig && (
            <div className="config-panel">
              <p style={{fontSize: '0.8rem', color: 'var(--text-secondary)'}}>
                This app uses Supabase for authentication. Ensure you have created users in your Supabase Auth dashboard.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default LoginScreen;
