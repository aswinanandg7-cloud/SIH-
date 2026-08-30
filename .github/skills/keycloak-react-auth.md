# Skill: Keycloak REST Authentication & Role-Based Access Control in React (Vite)

This guide documents the architecture, configuration, and best practices for integrating Keycloak authentication and role-based access control (RBAC) in React applications built with Vite.

---

## 1. Architecture Overview

- **Authentication Protocol**: Keycloak OpenID Connect Direct Access Grants (`grant_type=password`).
- **Endpoint**: `/realms/{realm}/protocol/openid-connect/token`
- **State Management**: Centralized React Context (`AuthContext.tsx`).
- **JWT Decoding**: Client-side base64 payload decoding to extract user details and roles (`realm_access.roles` and `resource_access.*.roles`).

---

## 2. Keycloak Admin Console Setup Checklist

When setting up Keycloak (`http://localhost:8080`) for frontend applications:

1. **Create Realm & Users**:
   - Create users with non-temporary passwords.
2. **Create Realm Roles**:
   - Define custom roles (e.g. `govt-agri-officer`) under **Realm Roles** and assign them to target users under **Role mapping**.
3. **Configure Frontend Client (`sih-frontend`)**:
   - Navigate to **Clients** -> **Create Client**.
   - **Client ID**: `sih-frontend` (or custom name).
   - **Client authentication**: `OFF` (Public client).
   - **Direct access grants**: `ON` (Required for username/password REST auth).
   - **Valid redirect URIs**: `http://localhost:5173/*` or `*`
   - **Web origins**: `+` or `*` (Allows browser cross-origin requests).

---

## 3. Resolving CORS & "Invalid Origin" in Vite

To prevent browser CORS blocks and Keycloak's `{ "error": "Invalid origin" }` during development, configure a proxy in `vite.config.ts`:

```ts
// vite.config.ts
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/realms': {
        target: 'http://localhost:8080',
        changeOrigin: true,
        secure: false,
        headers: {
          Origin: 'http://localhost:8080', // Rewrites Origin header for dev proxy
        },
      },
    },
  },
})
```

In `AuthContext.tsx`, fetch using a relative path when targeting local Keycloak:
```ts
const tokenEndpoint = keycloakUrl.includes('localhost:8080')
  ? `/realms/${realm}/protocol/openid-connect/token`
  : `${keycloakUrl.replace(/\/$/, '')}/realms/${realm}/protocol/openid-connect/token`;
```

---

## 4. Single-Place Auth Context Pattern (`AuthContext.tsx`)

```tsx
import React, { createContext, useContext, useState, useEffect } from 'react';
import type { User, AuthState, KeycloakTokenResponse, KeycloakJWTPayload } from '../types/auth';

interface AuthContextType extends AuthState {
  login: (username: string, password: string) => Promise<boolean>;
  logout: () => void;
  clearError: () => void;
}

function parseJwt(token: string): KeycloakJWTPayload | null {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    return JSON.parse(decodeURIComponent(escape(atob(base64))));
  } catch {
    return null;
  }
}

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [authError, setAuthError] = useState<string | null>(null);

  const login = async (username: string, password: string): Promise<boolean> => {
    setIsLoading(true);
    setAuthError(null);

    const tokenEndpoint = `/realms/master/protocol/openid-connect/token`;

    try {
      const formData = new URLSearchParams();
      formData.append('grant_type', 'password');
      formData.append('client_id', 'sih-frontend');
      formData.append('username', username);
      formData.append('password', password);

      const response = await fetch(tokenEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: formData.toString(),
      });

      if (!response.ok) {
        const errorText = await response.text();
        let errorData: any = null;
        try { errorData = JSON.parse(errorText); } catch {}
        setAuthError(errorData?.error_description || 'Authentication failed');
        setIsLoading(false);
        return false;
      }

      const data: KeycloakTokenResponse = await response.json();
      const payload = parseJwt(data.access_token);
      const roles = payload?.realm_access?.roles || [];

      setUser({
        username: payload?.preferred_username || username,
        roles,
      });
      setIsLoading(false);
      return true;
    } catch (err) {
      setAuthError('Network error connecting to Keycloak server');
      setIsLoading(false);
      return false;
    }
  };

  const logout = () => setUser(null);

  return (
    <AuthContext.Provider value={{ user, isAuthenticated: !!user, isLoading, authError, login, logout, clearError: () => setAuthError(null) }}>
      {children}
    </AuthContext.Provider>
  );
};
```

---

## 5. Role-Based View Guard Pattern (`App.tsx`)

```tsx
const MainContent: React.FC = () => {
  const { isAuthenticated, user } = useAuth();

  if (!isAuthenticated || !user) return <LoginScreen />;

  const hasOfficerRole = user.roles?.includes('govt-agri-officer');

  if (hasOfficerRole) {
    return <ProcurementPlanning />;
  }

  return <AccessDenied />;
};
```
