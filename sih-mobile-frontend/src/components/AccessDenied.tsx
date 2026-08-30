import React from 'react';
import { useAuth } from '../context/AuthContext';
import './AccessDenied.css';

export const AccessDenied: React.FC = () => {
  const { user, logout } = useAuth();

  return (
    <div className="access-denied-wrapper">
      <div className="denied-card">
        <div className="denied-icon-container">
          <span className="denied-icon">🚫</span>
        </div>

        <h1 className="denied-title">Access Restricted</h1>
        <p className="denied-subtitle">
          Your Keycloak account (<strong>{user?.username}</strong>) does not have the required permission to access the Procurement Planning Module.
        </p>

        <div className="required-role-box">
          <span className="role-label">Required Role:</span>
          <code className="role-badge required">govt-agri-officer</code>
        </div>

        <div className="user-roles-box">
          <span className="user-roles-title">Your Assigned Keycloak Roles:</span>
          <div className="roles-list">
            {user?.roles && user.roles.length > 0 ? (
              user.roles.map((role) => (
                <span key={role} className="role-badge assigned">
                  {role}
                </span>
              ))
            ) : (
              <span className="no-roles-text">No active roles found in Keycloak token</span>
            )}
          </div>
        </div>

        <button type="button" className="switch-user-btn" onClick={logout}>
          🔄 Logout & Login with Official Credentials
        </button>
      </div>
    </div>
  );
};
