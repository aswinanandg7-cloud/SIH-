import React from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { LoginScreen } from './components/LoginScreen';
import { ProcurementPlanning } from './components/ProcurementPlanning';
import { ClerkDashboard } from './components/ClerkDashboard';
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

  const userRoles = user.roles || [];

  const hasOfficerRole = userRoles.some(
    (role) => role.toLowerCase() === 'govt-agri-officer'
  );

  const hasClerkRole = userRoles.some(
    (role) => role.toLowerCase() === 'govt-agri-clerk'
  );

  // Route 2: Authenticated with govt-agri-officer -> Procurement Planning Dashboard
  if (hasOfficerRole) {
    return <ProcurementPlanning />;
  }

  // Route 3: Authenticated with govt-agri-clerk -> Clerk Dashboard (Procurement Planner & Live Report)
  if (hasClerkRole) {
    return <ClerkDashboard />;
  }


  // Route 4: Authenticated without required roles -> Access Denied error screen
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
