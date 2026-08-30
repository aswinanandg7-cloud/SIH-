export interface User {
  username: string;
  name?: string;
  email?: string;
  roles: string[];
}

export interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  authError: string | null;
}

export interface KeycloakTokenResponse {
  access_token: string;
  expires_in: number;
  refresh_expires_in?: number;
  refresh_token?: string;
  token_type: string;
  id_token?: string;
  scope?: string;
}

export interface KeycloakJWTPayload {
  sub?: string;
  preferred_username?: string;
  name?: string;
  email?: string;
  realm_access?: {
    roles: string[];
  };
  resource_access?: Record<string, { roles: string[] }>;
}

export interface ProcurementPlanItem {
  id: string;
  district: string;
  cropType: 'Wheat' | 'Paddy (Rice)' | 'Pulses' | 'Maize' | 'Mustard';
  targetQuantityTons: number;
  procuredQuantityTons: number;
  status: 'Planning' | 'Active' | 'Completed' | 'Pending Review';
  mspPerQuintal: number;
  allocatedBudgetLakhs: number;
  startDate: string;
  endDate: string;
}
