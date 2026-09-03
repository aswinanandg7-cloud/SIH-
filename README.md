# SIH — Government Agricultural Product Procurement System

A mobile-ready web portal designed for agricultural product procurement, slot booking, and queue management. The platform features Keycloak identity management, role-based access control (RBAC), a FastAPI backend service, and a React + TypeScript mobile frontend.

---

## 📋 Table of Contents
1. [Software Requirements](#-1-software-requirements)
2. [How to Start the App on a New Computer](#-2-how-to-start-the-app-on-a-new-computer)
3. [How to Debug & Make Production Deployments](#-3-how-to-debug--make-production-deployments)

---

## 🛠️ 1. Software Requirements

Before setting up the project on a new system, ensure you have the following installed:

| Tool / Technology | Minimum Version | Required For |
| :--- | :--- | :--- |
| **Git** | `v2.25+` | Source code management |
| **Node.js** | `v18.0.0+` (LTS recommended) | Frontend runtime environment |
| **npm** | `v9.0.0+` | Frontend package management |
| **Python** | `v3.9+` | Backend server (`FastAPI`) |
| **pip** | `v21.0+` | Python package management |
| **Docker Engine** | `v20.10+` | Containerizing Keycloak & PostgreSQL |
| **Docker Compose** | `v2.0+` | Multi-container orchestration |

---

## 🚀 2. How to Start the App on a New Computer

Follow these steps sequentially to set up and run the entire application stack on a new computer.

### Step 1: Clone the Repository
```bash
git clone (https://github.com/aswinanandg7-cloud/SIH-.git)
cd SIH-
```

---

### Step 2: Start Keycloak & PostgreSQL (Identity Provider)

1. **Navigate to the Keycloak directory and launch containers:**
   ```bash
   cd keycloak
   docker compose up -d
   ```
2. **Verify containers are running:**
   ```bash
   docker compose ps
   ```
   *Keycloak will be accessible at `http://localhost:8080`.*

3. **Configure Keycloak Realm & Client:**
   - Log in to **[http://localhost:8080/admin](http://localhost:8080/admin)** (Credentials: `admin` / `admin`).
   - Create/Select your realm (e.g., `master` or a custom realm).
   - Go to **Clients** ➡️ **Create Client**:
     - **Client ID**: `sih-frontend`
     - **Client Authentication**: `OFF` (Public Client)
     - **Direct Access Grants**: `ON` (Required for REST login)
     - **Valid Redirect URIs**: `http://localhost:5173/*`
     - **Web Origins**: `*` (or `+`)
   - Go to **Realm Roles** ➡️ **Create Role**:
     - Add `govt-agri-officer` (Procurement Planning access)
     - Add `govt-agri-clerk` (Slot Visibility & Token Verification access)
   - Go to **Users** ➡️ **Add User**:
     - Create user (e.g. `officer1` / `clerk1`), set password under **Credentials** (turn **Temporary** OFF), and assign their corresponding role under **Role Mapping**.

---

### Step 3: Start the Backend Service (`FastAPI`)

1. **Open a new terminal window** and navigate to `sih-backend`:
   ```bash
   cd sih-backend
   ```
2. **Create and activate a virtual environment:**
   ```bash
   # Linux/macOS
   python3 -m venv venv
   source venv/bin/activate

   # Windows
   python -m venv venv
   .\venv\Scripts\activate
   ```
3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
4. **Start the FastAPI server:**
   ```bash
   uvicorn main:app --reload --port 8000
   ```
   *The backend API will run at `http://localhost:8000` with interactive documentation at `http://localhost:8000/docs`.*

---

### Step 4: Start the Mobile Frontend (`React + Vite`)

1. **Open another terminal window** and navigate to `sih-mobile-frontend`:
   ```bash
   cd sih-mobile-frontend
   ```
2. **Install Node dependencies:**
   ```bash
   npm install
   ```
3. **Run the Vite development server:**
   ```bash
   npm run dev
   ```
4. **Access the application:**
   Open your browser and navigate to **`http://localhost:5173`**.

---

## 🔍 3. How to Debug & Make Production Deployments

### 🛠️ Debugging Guide

#### 1. Frontend Debugging
- **Vite Proxy Inspection:** Frontend API calls to `/api/*` and `/realms/*` are forwarded via Vite proxy (`vite.config.ts`). If requests fail, verify target URLs (`http://localhost:8000` and `http://localhost:8080`).
- **Browser Developer Tools:**
  - Check **Console** for JavaScript or authentication state errors.
  - Inspect **Network** tab for HTTP status codes (`401 Unauthorized`, `403 Forbidden`, `404 Not Found`).
  - Verify JWT payload structure in `localStorage` or memory to confirm role assignments (`realm_access.roles`).

#### 2. Backend Debugging
- **Interactive Swagger Docs:** Access `http://localhost:8000/docs` to test endpoints (`GET /slots`, `POST /book`, `POST /verify/{token}`) independently of the UI.
- **Verbose Server Logs:** Run Uvicorn with debug logging enabled:
  ```bash
  uvicorn main:app --reload --port 8000 --log-level debug
  ```

#### 3. Keycloak & Database Debugging
- **Container Logs:** Inspect real-time container startup or authentication logs:
  ```bash
  cd keycloak
  docker compose logs -f keycloak
  docker compose logs -f postgres
  ```
- **Common Issues & Fixes:**
  - `Invalid origin` / CORS Error: Ensure **Web Origins** in Keycloak client settings is set to `*` or `+`.
  - `Direct grant not enabled`: Ensure **Direct Access Grants** toggle is switched ON in client `sih-frontend`.
  - Database connection failures: Verify `POSTGRES_USER` and `POSTGRES_PASSWORD` match in `docker-compose.yml`.

---

### 🚀 Production Deployment Guide

#### Architectural Overview
In production, all services should run behind a reverse proxy (e.g., **Nginx**, **Caddy**, or an API Gateway) with SSL/TLS (HTTPS) termination.

```
                  ┌────────────────────────┐
                  │    Nginx / TLS (443)   │
                  └───────────┬────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         ▼                    ▼                    ▼
┌─────────────────┐  ┌──────────────────┐  ┌────────────────┐
│  Static React   │  │  FastAPI Backend │  │ Keycloak IAM   │
│  (Dist Build)   │  │   (Gunicorn/     │  │  (Production   │
│                 │  │    Uvicorn)      │  │     Mode)      │
└─────────────────┘  └──────────────────┘  └────────────────┘
```

#### 1. Keycloak Production Deployment
- Switch Keycloak from `start-dev` to `start` mode.
- Set production environment variables in `docker-compose.yml` or container secrets:
  - `KC_HOSTNAME`: Your public domain (e.g., `auth.yourdomain.com`).
  - `KC_HTTP_ENABLED`: `false` (enforce HTTPS).
  - Change default admin password (`KEYCLOAK_ADMIN_PASSWORD`).
- Use an managed database instance (e.g., AWS RDS PostgreSQL) or secure persistent volume backups.

#### 2. Backend Production Deployment (`FastAPI`)
- Run FastAPI using **Gunicorn** with **Uvicorn workers** for concurrency:
  ```bash
  gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
  ```
- Manage process lifecycle via **Systemd** or containerize with Docker:
  ```dockerfile
  FROM python:3.11-slim
  WORKDIR /app
  COPY requirements.txt .
  RUN pip install --no-cache-dir -r requirements.txt
  COPY . .
  CMD ["gunicorn", "main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
  ```

#### 3. Frontend Production Deployment (`React + Vite`)
- Build the optimized static distribution bundle:
  ```bash
  cd sih-mobile-frontend
  npm run build
  ```
- Deploy the contents of the generated `./dist` directory to an Nginx server, AWS S3 + CloudFront, or Vercel/Netlify.
- Sample Nginx reverse proxy configuration for Vite single-page application and API routing:
  ```nginx
  server {
      listen 80;
      server_name app.yourdomain.com;

      root /var/www/sih-mobile-frontend/dist;
      index index.html;

      location / {
          try_files $uri $uri/ /index.html;
      }

      location /api/ {
          proxy_pass http://127.0.0.1:8000/;
          proxy_set_header Host $host;
          proxy_set_header X-Real-IP $remote_addr;
      }
  }
  ```

#### 4. Production Security Checklist
- [ ] Enforce HTTPS across all frontend and backend endpoints.
- [ ] Restrict CORS origins in FastAPI `CORSMiddleware` to exact frontend production domains instead of `*`.
- [ ] Use environment variables (`.env`) for secrets; never hardcode credentials.
- [ ] Configure rate limiting on backend endpoints and Keycloak login routes.
