/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useContext, useState, useEffect } from 'react';
import { createClient } from '@supabase/supabase-js';
import type { Session } from '@supabase/supabase-js';
import type { User, AuthState } from '../types/auth';

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || 'https://zexopndvszrerifbizyt.supabase.co';
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY || 'sb_publishable_ja7dpfyqvl26lmJtsZSYcg_X2UIiioD';

const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

interface AuthContextType extends AuthState {
  login: (email: string, password: string) => Promise<boolean>;
  logout: () => void;
  clearError: () => void;
  demoLogin: (role: 'govt-agri-officer' | 'govt-agri-clerk' | 'general-user') => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [authError, setAuthError] = useState<string | null>(null);

  const handleSession = (session: Session) => {
    setToken(session.access_token);
    
    // Extract roles from user metadata
    const rawRoles = session.user.user_metadata?.roles || session.user.app_metadata?.roles || [];
    const roles = Array.isArray(rawRoles) ? rawRoles : [rawRoles];
    
    setUser({
      username: session.user.email?.split('@')[0] || 'user',
      name: session.user.user_metadata?.full_name || session.user.email?.split('@')[0] || 'User',
      email: session.user.email || '',
      roles: roles,
    });
  };

  // Initialize session from Supabase
  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session) {
        handleSession(session);
      }
      setIsLoading(false);
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      if (session) {
        handleSession(session);
      } else {
        setUser(null);
        setToken(null);
      }
      setIsLoading(false);
    });

    return () => subscription.unsubscribe();
  }, []);

  const login = async (email: string, password: string): Promise<boolean> => {
    setIsLoading(true);
    setAuthError(null);

    // Support usernames by appending a default domain if no @ is present
    const loginEmail = email.includes('@') ? email : `${email}@agri.gov.in`;

    const { data, error } = await supabase.auth.signInWithPassword({
      email: loginEmail,
      password,
    });

    if (error) {
      console.warn('Supabase auth error:', error.message);
      setAuthError(`Authentication Failed: ${error.message}`);
      setIsLoading(false);
      return false;
    }
    
    if (data.session) {
      handleSession(data.session);
    }
    setIsLoading(false);
    return true;
  };

  const demoLogin = (role: 'govt-agri-officer' | 'govt-agri-clerk' | 'general-user') => {
    setIsLoading(true);
    setAuthError(null);

    setTimeout(() => {
      let demoRoles: string[];
      let demoUsername: string;
      let demoName: string;
      let demoEmail: string;

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
      setIsLoading(false);
    }, 600);
  };

  const logout = async () => {
    await supabase.auth.signOut();
    setUser(null);
    setToken(null);
    setAuthError(null);
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
