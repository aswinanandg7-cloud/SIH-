# SIH Mobile Frontend — Agricultural Procurement Portal

Mobile-first React + TypeScript web application powered by Vite, integrated with Keycloak for OpenID Connect REST authentication and FastAPI for procurement slot booking and token verification.

---

## 🛠️ 1. Software Requirements

- **Node.js**: `v18.0.0+` or `v20.0.0+` (LTS recommended)
- **npm**: `v9.0.0+`
- **Keycloak Service**: Running at `http://localhost:8080` (See root [README.md](../README.md))
- **FastAPI Backend**: Running at `http://localhost:8000` (See root [README.md](../README.md))

---

## 🚀 2. How to Start on a New Computer

1. **Install Dependencies:**
   ```bash
   npm install
   ```

2. **Run Development Server:**
   ```bash
   npm run dev
   ```
   *Access the app at `http://localhost:5173`.*

   > **Note on Vite Proxy:** `/realms/*` calls are proxied to Keycloak (`http://localhost:8080`) and `/api/*` calls are proxied to FastAPI (`http://localhost:8000`).

3. **Available Scripts:**
   - `npm run dev`: Starts local development server with HMR.
   - `npm run build`: Compiles TypeScript and builds production distribution artifacts into `dist/`.
   - `npm run preview`: Previews locally built production bundle.
   - `npm run lint`: Runs ESLint check across source code.

---

## 🔍 3. Debugging & Production Deployments

### 🛠️ Debugging
- **Network Tab:** Verify `/realms/master/protocol/openid-connect/token` returns a 200 status code with JWT `access_token`.
- **Keycloak Roles:** Check role assignments in parsed JWT (`govt-agri-officer` or `govt-agri-clerk`).
- **Dev Server Proxy:** Ensure Keycloak (`8080`) and FastAPI (`8000`) services are active prior to starting Vite.

### 🚀 Production Deployment
1. Build production bundle:
   ```bash
   npm run build
   ```
2. Serve static output inside `./dist` using Nginx, Caddy, or static cloud hosting (Vercel, Netlify, AWS S3/CloudFront).
3. Refer to the **[Master README.md](../README.md)** for full system deployment and Nginx reverse proxy configuration.
