import React from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { LoginScreen } from './components/LoginScreen';
import { ProcurementPlanning } from './components/ProcurementPlanning';
import { AccessDenied } from './components/AccessDenied';
import './App.css';

const MainContent: React.FC = () => {
  const { isAuthenticated, user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="app-loading-screen">
        <div className="app-spinner"></div>
        <p>Connecting to Keycloak...</p>
      </div>
    );
  }

  // Route 1: Unauthenticated -> Login Screen
  if (!isAuthenticated || !user) {
    return <LoginScreen />;
  }

  // Check for the required role 'govt-agri-officer'
  const REQUIRED_ROLE = 'govt-agri-officer';
  const hasOfficerRole = user.roles?.some(
    (role) => role.toLowerCase() === REQUIRED_ROLE.toLowerCase()
  );

  // Route 2: Authenticated with govt-agri-officer -> Procurement Planning Dashboard
  if (hasOfficerRole) {
    return <ProcurementPlanning />;
  }

  // Route 3: Authenticated without required role -> Access Denied error screen
  return <AccessDenied />;
};

function App() {
  return (
    <AuthProvider>
      <MainContent />
    </AuthProvider>
  );
}

export default App;
