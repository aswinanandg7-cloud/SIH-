import React, { createContext, useContext, useState, useEffect } from 'react';
import type { User, AuthState, KeycloakTokenResponse, KeycloakJWTPayload } from '../types/auth';

interface AuthContextType extends AuthState {
  login: (username: string, password: string) => Promise<boolean>;
  logout: () => void;
  clearError: () => void;
  keycloakUrl: string;
  realm: string;
  setRealm: (realm: string) => void;
  clientId: string;
  setClientId: (clientId: string) => void;
  demoLogin: (role: 'govt-agri-officer' | 'govt-agri-clerk' | 'general-user') => void;
}

const DEFAULT_KEYCLOAK_URL = 'http://localhost:8080';
const DEFAULT_REALM = 'master';
const DEFAULT_CLIENT_ID = 'sih-frontend';

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Helper function to decode JWT payload safely
function parseJwt(token: string): KeycloakJWTPayload | null {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    return JSON.parse(jsonPayload);
  } catch (error) {
    console.error('Failed to parse JWT token', error);
    return null;
  }
}

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [authError, setAuthError] = useState<string | null>(null);

  const [keycloakUrl] = useState<string>(DEFAULT_KEYCLOAK_URL);
  const [realm, setRealm] = useState<string>(
    localStorage.getItem('kc_realm') || DEFAULT_REALM
  );
  const [clientId, setClientId] = useState<string>(
    localStorage.getItem('kc_client_id') || DEFAULT_CLIENT_ID
  );

  // Restore session from localStorage if present
  useEffect(() => {
    const storedToken = localStorage.getItem('kc_access_token');
    const storedUser = localStorage.getItem('kc_user_data');

    if (storedToken && storedUser) {
      try {
        setToken(storedToken);
        setUser(JSON.parse(storedUser));
      } catch {
        localStorage.removeItem('kc_access_token');
        localStorage.removeItem('kc_user_data');
      }
    }
  }, []);

  const handleRealmChange = (newRealm: string) => {
    setRealm(newRealm);
    localStorage.setItem('kc_realm', newRealm);
  };

  const handleClientIdChange = (newClientId: string) => {
    setClientId(newClientId);
    localStorage.setItem('kc_client_id', newClientId);
  };

  const login = async (username: string, password: string): Promise<boolean> => {
    setIsLoading(true);
    setAuthError(null);

    // Use relative path for proxied local Keycloak requests to bypass browser CORS policies
    const tokenEndpoint = keycloakUrl.includes('localhost:8080')
      ? `/realms/${realm}/protocol/openid-connect/token`
      : `${keycloakUrl.replace(/\/$/, '')}/realms/${realm}/protocol/openid-connect/token`;

    try {
      const formData = new URLSearchParams();
      formData.append('grant_type', 'password');
      formData.append('client_id', clientId);
      formData.append('username', username);
      formData.append('password', password);

      const response = await fetch(tokenEndpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: formData.toString(),
      });

      if (!response.ok) {
        const errorText = await response.text().catch(() => '');
        let errorData: any = null;
        try {
          errorData = JSON.parse(errorText);
        } catch {
          // Response was not JSON
        }

        console.warn('Keycloak authentication error details:', response.status, errorData || errorText);

        let errorMessage = errorData?.error_description || errorData?.error;

        if (!errorMessage) {
          if (response.status === 403) {
            errorMessage = '403 Forbidden: Keycloak rejected the request. Ensure "Direct Access Grants" is enabled for your client in Keycloak, or check your Client ID in Keycloak Settings below.';
          } else if (response.status === 401) {
            errorMessage = '401 Unauthorized: Invalid username or password.';
          } else {
            errorMessage = `Keycloak returned status ${response.status}. ${errorText}`;
          }
        } else if (errorData?.error === 'unauthorized_client') {
          errorMessage = `Unauthorized Client: ${errorData.error_description || 'Direct Access Grants are not enabled for this Keycloak client.'}`;
        }

        setAuthError(errorMessage);
        setIsLoading(false);
        return false;
      }

      const data: KeycloakTokenResponse = await response.json();
      const accessToken = data.access_token;
      const parsedPayload = parseJwt(accessToken);

      // Extract roles from realm_access and resource_access
      const realmRoles = parsedPayload?.realm_access?.roles || [];
      let clientRoles: string[] = [];
      if (parsedPayload?.resource_access) {
        Object.values(parsedPayload.resource_access).forEach((res) => {
          if (res?.roles) {
            clientRoles = [...clientRoles, ...res.roles];
          }
        });
      }

      const allRoles = Array.from(new Set([...realmRoles, ...clientRoles]));

      const userData: User = {
        username: parsedPayload?.preferred_username || username,
        name: parsedPayload?.name || username,
        email: parsedPayload?.email || '',
        roles: allRoles,
      };

      setToken(accessToken);
      setUser(userData);

      localStorage.setItem('kc_access_token', accessToken);
      localStorage.setItem('kc_user_data', JSON.stringify(userData));

      setIsLoading(false);
      return true;
    } catch (err: any) {
      console.error('Keycloak authentication network error:', err);
      setAuthError(
        `Unable to reach Keycloak at ${keycloakUrl}. Make sure Keycloak is running at http://localhost:8080 or test using Demo Mode below.`
      );
      setIsLoading(false);
      return false;
    }
  };

  // Demo login for testing when local Keycloak instance is offline or for quick preview
  const demoLogin = (role: 'govt-agri-officer' | 'govt-agri-clerk' | 'general-user') => {
    setIsLoading(true);
    setAuthError(null);

    setTimeout(() => {
      let demoRoles: string[] = [];
      let demoUsername = '';
      let demoName = '';
      let demoEmail = '';

      if (role === 'govt-agri-officer') {
        demoRoles = ['govt-agri-officer', 'default-roles-realm', 'offline_access'];
        demoUsername = 'agri_officer_demo';
        demoName = 'Rajesh Kumar (Agri Officer)';
        demoEmail = 'officer.rajesh@agri.gov.in';
      } else if (role === 'govt-agri-clerk') {
        demoRoles = ['govt-agri-clerk', 'default-roles-realm', 'offline_access'];
        demoUsername = 'agri_clerk_demo';
        demoName = 'Anita Sharma (Agri Clerk)';
        demoEmail = 'clerk.anita@agri.gov.in';
      } else {
        demoRoles = ['farmer-user', 'default-roles-realm'];
        demoUsername = 'farmer_user_demo';
        demoName = 'Suresh Patel (Farmer)';
        demoEmail = 'suresh.farmer@mail.com';
      }

      const demoUser: User = {
        username: demoUsername,
        name: demoName,
        email: demoEmail,
        roles: demoRoles,
      };

      setToken('demo_jwt_token_simulation');
      setUser(demoUser);
      localStorage.setItem('kc_access_token', 'demo_jwt_token_simulation');
      localStorage.setItem('kc_user_data', JSON.stringify(demoUser));
    }, 600);
  };

  const logout = () => {
    setUser(null);
    setToken(null);
    setAuthError(null);
    localStorage.removeItem('kc_access_token');
    localStorage.removeItem('kc_user_data');
  };

  const clearError = () => setAuthError(null);

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!user,
        isLoading,
        authError,
        login,
        logout,
        clearError,
        keycloakUrl,
        realm,
        setRealm: handleRealmChange,
        clientId,
        setClientId: handleClientIdChange,
        demoLogin,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
