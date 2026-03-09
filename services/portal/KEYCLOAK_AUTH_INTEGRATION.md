# Keycloak OAuth2/OIDC Authentication Integration

## Overview
Keycloak is the authentication provider for the DigitalTWINS Portal. The frontend supports form-based login through the backend as well as Keycloak SSO via keycloak-js utilities. RBAC is enforced for three roles: admin, researcher, and clinician.

## Keycloak Configuration

Server: https://130.216.216.243:8009
Realm: digitaltwins
Client ID: digitaltwins-portal
User groups: admin, researcher, clinician

## Frontend Implementation

### Configuration
frontend/.env (template in .env.example)

```
VITE_KEYCLOAK_URL=https://130.216.216.243:8009
VITE_KEYCLOAK_REALM=digitaltwins
VITE_KEYCLOAK_CLIENT_ID=api
```

### Keycloak Utilities (frontend/src/plugins/keycloak.ts)
Centralized Keycloak client helper:
- initKeycloak()
- getAccessToken()
- getUserRoles()
- hasRole(role)
- logout()

### Auth Store (frontend/src/store/auth_store.ts)
Global auth state backed by Pinia:
- isLoggedIn
- user (username, email, givenName, familyName, roles)
- accessToken
- hasAdminRole / hasResearcherRole / hasClinicianRole

The store also parses JWT from sessionStorage when Keycloak SSO is not active.

### Login Flow (frontend/src/views/login/index.vue)
Form-based login posts to:
- POST /api/auth/login-keycloak

On success:
- access_token stored in sessionStorage
- auth store updated
- redirected to /home

### Router Guards (frontend/src/router/index.ts)
- Routes with meta.requiresAuth are protected.
- Users are redirected to / if unauthenticated.
- Dashboard routes are role-gated:
  - Study dashboard: admin or researcher
  - Clinician dashboard: admin or clinician
  - Multi-role users have access to all dashboards matching their roles

### HTTP Client (frontend/src/plugins/http.ts)
- Adds Authorization: Bearer <token> on each request
- Handles 401 with refresh attempts and redirects to login on failure

## Backend Implementation

### Keycloak Client (backend/app/client/keycloak.py)
- Verifies JWT with Keycloak public key (RS256)
- Extracts user info and roles
- Filters roles to admin, researcher, clinician

### Auth Utilities (backend/app/utils/auth.py)
- get_current_user dependency
- require_role(role) factory

### Auth Endpoints (backend/app/main.py)
- POST /api/auth/login-keycloak
  - Exchanges user credentials for a real Keycloak token
- GET /api/auth/user
  - Returns current user info when authenticated

## Role-Based Access Control

Role access rules:
- admin: all dashboards
- researcher: study dashboard only
- clinician: clinician dashboard only
- multi-role: union of allowed dashboards

## Testing

1) Start frontend and backend.
2) Login via form and confirm access_token in sessionStorage.
3) Verify dashboard visibility by role.
4) Confirm direct URL access is blocked when role is missing.

## Troubleshooting

- 401 on API calls: check Authorization header and token validity.
- Roles missing: verify user group assignment in Keycloak and re-login.
- Redirect loops: check router guard and token presence.
- **FastAPI Security:** https://fastapi.tiangolo.com/tutorial/security/
