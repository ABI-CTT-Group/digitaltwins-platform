# Keycloak Authentication Quick Start Guide

## Prerequisites
- Keycloak server available and reachable
- Realm: digitaltwins
- User groups: admin, researcher, clinician
- Client: api

## Frontend Setup

### 1) Create Environment File

```bash
cd frontend
cp .env.example .env
```

frontend/.env:

```
VITE_KEYCLOAK_URL=https://130.216.216.243:8009
VITE_KEYCLOAK_REALM=digitaltwins
VITE_KEYCLOAK_CLIENT_ID=api
```

### 2) Install Dependencies

```bash
cd frontend
npm install
```

### 3) Run Development Server

```bash
npm run dev
```

The app runs at http://localhost:5173 by default.

### 4) Login

1) Open http://localhost:5173
2) Sign in with username and password
3) You will be redirected to /home on success
4) The navbar shows your name and roles

## Backend Setup

### 1) Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2) Run Development Server

```bash
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

### 3) Test Authentication

```bash
# Token is stored in Session Storage: access_token

curl -H "Authorization: Bearer <YOUR_TOKEN>" \
  http://localhost:8000/api/auth/user
```

## User Assignment in Keycloak

1) Open Keycloak admin console
2) Select the digitaltwins realm
3) Users -> select a user -> Groups
4) Join group: admin, researcher, or clinician

Roles appear in JWT under realm_access.roles.

## Role-Based Dashboards

- admin: all dashboards
- researcher: study dashboard only
- clinician: clinician dashboard only
- multi-role: union of allowed dashboards

## Troubleshooting

### Login fails immediately
- Check backend is running and /api/auth/login-keycloak is reachable

### 401 Unauthorized on API calls
- Confirm Authorization header is present
- Confirm access_token in sessionStorage is valid

### Roles missing
- Verify group membership in Keycloak
- Logout and login again

## Key Files

Frontend:
- src/views/login/index.vue
- src/store/auth_store.ts
- src/plugins/http.ts

Backend:
- app/client/keycloak.py
- app/utils/auth.py
- app/main.py

## Support

For Keycloak server issues, contact the devops team.
