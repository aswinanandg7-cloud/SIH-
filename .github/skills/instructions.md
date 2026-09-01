# Project Instructions & Feature Reference (`instructions.md`)

This document serves as the comprehensive context, architectural guide, and coding guidelines for the **AgroProcure** platform (SIH Agricultural Procurement & Token Management System).

---

## 1. Project Context & Tech Stack

### Project Overview
**AgroProcure** is a mobile-responsive agricultural procurement management web application designed for government officers, clerks, and farmers. It streamlines center-wise procurement target planning, token distribution, slot booking, and live capacity tracking.

### Tech Stack
- **Frontend (`sih-mobile-frontend`)**:
  - **Framework**: React 18 + TypeScript + Vite.
  - **Styling**: Modern Vanilla CSS with dark mode aesthetics, glassmorphism, flex/grid layouts, responsive drawer navigation, and status badges.
  - **Authentication**: Keycloak OpenID Connect Direct Access Grants (`grant_type=password`) with client-side JWT role decoding.
- **Backend (`sih-backend`)**:
  - **Framework**: FastAPI (Python 3.10+), served via `uvicorn main:app --reload --port 8000`.
  - **Database**: SQLite (`agroprocure.db`) with `PRAGMA foreign_keys = ON`.
- **Identity & Access Management (`keycloak`)**:
  - Keycloak 26.x running via Docker on port `8080`.
  - **Realm**: `master`
  - **Client ID**: `sih-frontend` (Public Client, Direct Access Grants enabled).

---

## 2. Completed Features & Implementation Details

### A. Keycloak REST Authentication & RBAC
- **`AuthContext.tsx`**: Manages authentication state, token storage, and JWT base64 payload decoding (`parseJwt`). Extracts roles from `realm_access.roles` and `resource_access.*.roles`.
- **`LoginScreen.tsx`**: Mobile-optimized login interface supporting direct Keycloak password grants with error handling and demo role credentials helper.
- **Role-Based Routing (`App.tsx`)**:
  - `Unauthenticated` ➔ `<LoginScreen />`
  - `govt-agri-officer` ➔ `<ProcurementPlanning />`
  - `govt-agri-clerk` ➔ `<ClerkDashboard />`
  - `Other / Missing Role` ➔ `<AccessDenied />`

### B. Govt Agri Officer Dashboard (`ProcurementPlanning.tsx`)
- High-level procurement planning dashboard for state/district officers.
- District target management, MSP (Minimum Support Price) rates, allocated budget calculations in Lakhs, crop filters (Wheat, Paddy, Pulses), search bar, and interactive plan creator modal.

### C. Govt Agri Clerk Dashboard & Dual-Page Navigation (`ClerkDashboard.tsx`)
Responsive layout featuring a collapsible **Side Navigation Panel** with two dedicated pages:

#### Page 1: "The Procurement Planner"
- **Date Selector**: `<input type="date">` for selecting the daily target planning date, with quick controls for "Today", previous day, and next day.
- **5 Procurement Centers**:
  - 2 Cereals Centers: `Center 1 - North Cereals Hub`, `Center 2 - Central Grain Silo`.
  - 3 Pulses Centers: `Center 3 - East Pulse Depot`, `Center 4 - South Legume Yard`, `Center 5 - West Gram Storage`.
- **Editable Capacity Limits**: Inline numeric inputs (`<input type="number">`) for editing each center's limit in metric tons before submitting.
- **KPI Summary**: Live calculated cards for Cereals Target (MT), Pulses Target (MT), and Total Day Limit (MT).
- **Backend Persistence**:
  - `POST /api/procurement-plan`: Persists daily center limits for the selected date into SQLite.
  - `GET /api/procurement-plan?date=YYYY-MM-DD`: Fetches saved plan for the target date. If no plan has been submitted for that date yet, it automatically prepopulates with the limits from the previous plan.

#### Page 2: "The Live Report"
- Real-time reporting mockup showing:
  - **Tokens Issued**: Total farmer tokens distributed today (1,420 Tokens across 5 centers).
  - **Procured Volume & Limit Filled**: Real-time capacity utilization percentage (e.g. 67.9% overall).
  - **Center Live Status Cards**: Card grid displaying center code, crop category, token count, capacity filled in tons, visual progress bars, operating status, and average queue wait times.

---

## 3. SQLite Database Schema & Backend APIs (`sih-backend/main.py`)

### Database Tables (`agroprocure.db`)
1. `slots`: Stores time slot capacity (`id`, `center`, `crop`, `time`, `max_capacity`).
2. `bookings`: Stores farmer token check-ins (`token`, `farmer_name`, `farmer_id`, `slot_id`, `crop`, `sub_queue_id`, `status`).
3. `procurement_plans`: Stores daily center limits (`id`, `date`, `center_id`, `center_name`, `category`, `limit_tons`, `created_at`, `UNIQUE(date, center_id)`).

### Core Endpoints
- `GET /slots`: Returns available slot capacity and booking stats.
- `POST /book`: Generates a unique token booking for a slot.
- `POST /verify/{token}`: Verifies farmer token on arrival.
- `GET /procurement-plan?date=YYYY-MM-DD`: Returns center limits for date or prepopulates from previous plan.
- `POST /procurement-plan`: Saves/upserts daily center procurement limits.

---

## 4. Future Coding Guidelines & Development Rules

### Rule 1: Dev Server Proxying
All frontend requests to FastAPI **MUST** use relative `/api/...` endpoints. The proxy configuration in `vite.config.ts` handles forwarding `/api` to `http://localhost:8000` and `/realms` to `http://localhost:8080`. Never hardcode `http://localhost:8000` directly in component fetch calls.

### Rule 2: Maintaining UI Aesthetics & Styling
- Keep design modern, clean, and wowed: dark background (`#0f172a`), card container backgrounds (`#1e293b`), borders (`#334155`), glassmorphism overlays, and rounded corners (`12px` to `16px`).
- Use category pills with explicit colors:
  - **Cereals**: Yellow badge (`background: rgba(234, 179, 8, 0.15); color: #facc15; border: 1px solid rgba(234, 179, 8, 0.3)`).
  - **Pulses**: Pink badge (`background: rgba(236, 72, 153, 0.15); color: #f472b6; border: 1px solid rgba(236, 72, 153, 0.3)`).
  - **Success / Saved**: Green badge (`color: #4ade80`).

### Rule 3: Extending RBAC & Adding Roles
- To add a new role:
  1. Register the role name in Keycloak console.
  2. Add role check in `App.tsx` (e.g. `userRoles.includes('your-new-role')`).
  3. Render the designated top-level component under `App.tsx`.

### Rule 4: SQLite Database Updates
- Always use `INSERT OR REPLACE` or `ON CONFLICT` when saving date-specific records to prevent duplicate key crashes.
- Always execute `init_db()` at script startup to ensure new tables/columns are automatically created.

### Rule 5: Running the System Locally
- **Keycloak**: Docker container listening on port `8080`.
- **Backend**: `python3 -m uvicorn main:app --reload --port 8000` (inside `sih-backend/`).
- **Frontend**: `npm run dev` (inside `sih-mobile-frontend/`).
