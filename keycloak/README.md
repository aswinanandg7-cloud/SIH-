# Keycloak Identity & Access Management Service

This directory contains the Docker Compose setup for running local Keycloak backed by PostgreSQL.

---

## 🛠️ 1. Prerequisites & Dependencies

Before running Keycloak, ensure you have the following installed:
- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)

---

## 🚀 2. Bringing Keycloak Up & Down

### Bring Service Up
From the project root or `keycloak/` directory:

```bash
cd keycloak
docker compose up -d
```

Keycloak will start up at **`http://localhost:8080`**. It may take ~15–30 seconds for the service to fully initialize.

### Check Container Status & Logs
```bash
# Check container status
docker compose ps

# View live container logs
docker compose logs -f keycloak
```

### Bring Service Down
To stop and remove containers while preserving your database data:

```bash
docker compose down
```

### Reset & Clear Database (Fresh Start)
To stop containers and wipe all stored realm data and users:

```bash
docker compose down -v
```

---

## 🔐 3. Default Admin Credentials

- **Admin Portal**: [http://localhost:8080](http://localhost:8080) (or `http://localhost:8080/admin`)
- **Admin Username**: `admin`
- **Admin Password**: `admin`

*PostgreSQL Database Info (Internal):*
- Host: `localhost:5432`
- Database: `keycloak`
- User: `keycloak`
- Password: `keycloak_password`

---

## ⚙️ 4. Creating Application Client (`sih-frontend`)

Our React mobile frontend connects to Keycloak using the REST OpenID Connect password grant. You must register the client in Keycloak:

1. Log in to **[http://localhost:8080/admin](http://localhost:8080/admin)** using `admin` / `admin`.
2. Select your target realm (e.g. `master` or custom realm).
3. Click **Clients** in the left menu ➡️ **Create client**.
4. **General Configuration**:
   - **Client ID**: `sih-frontend`
5. **Capability Config (CRITICAL)**:
   - **Client authentication**: Toggle **OFF** (Public client for React/Mobile apps).
   - **Direct access grants**: Toggle **ON** (Required for username/password login).
6. **Login Settings**:
   - **Valid redirect URIs**: Set to `http://localhost:5173/*` (or `http://localhost:5174/*` or `*`)
   - **Web origins**: Set to `+` or `*` (Prevents CORS / `Invalid origin` errors)
7. Click **Save**.

---

## 👤 5. Users & Roles Requirements

Our frontend enforces role-based routing depending on the JWT roles assigned to the user:

### Step 5a: Create Realm Roles
1. Navigate to **Realm Roles** in the left menu ➡️ **Create role**.
2. Create the following roles:
   - `govt-agri-officer`: Accesses the **Procurement Planning Portal**.
   - `govt-agri-clerk`: Accesses the **Token Slot Visibility Page**.

### Step 5b: Create User & Assign Roles
1. Navigate to **Users** ➡️ **Add user**.
2. Enter **Username** (e.g. `officer1` or `clerk1`). Click **Create**.
3. Go to the **Credentials** tab ➡️ Click **Set password**:
   - Enter a password and toggle **Temporary** to **OFF**. Click **Save**.
4. Go to the **Role mapping** tab ➡️ Click **Assign role**:
   - Select and assign `govt-agri-officer` or `govt-agri-clerk`.

---

## 🧪 Testing the Frontend Login

1. Start your frontend app (`npm run dev`).
2. Enter your created user's username and password.
3. Upon login, the app parses the Keycloak JWT and routes:
   - **`govt-agri-officer`** ➡️ Procurement Planning Dashboard
   - **`govt-agri-clerk`** ➡️ Token Slot Visibility Page
   - *Any other role* ➡️ Access Denied Error Screen
