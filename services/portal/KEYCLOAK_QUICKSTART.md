# Keycloak Authentication Quick Start Guide

## Prerequisites
- Keycloak server available and reachable
- Realm: digitaltwins
- User groups: admin, researcher, clinician
- Clients:
  - `portal-frontend` (public client for browser-based auth)
  - `api` (confidential client for backend operations)

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
VITE_KEYCLOAK_CLIENT_ID=portal-frontend
```

**Note**: 
Use `portal-frontend` (public client) for authentication directly with keycloak 
The  client `api` (confidential client) for authentication with keycloak via backend 

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

The login page offers two authentication methods:

**Method 1: Direct Keycloak Login (Recommended)**
1. Open http://localhost:5173
2. Click "Sign In with Keycloak" button
3. You'll be redirected to Keycloak's login page
4. Enter credentials on Keycloak (credentials never sent to backend)
5. Redirected back to portal on success

**Method 2: Traditional Form Login**
1. Open http://localhost:5173
2. Enter username and password in the form
3. Click "Sign In" button
4. Credentials sent to backend, backend authenticates with Keycloak
5. Access token returned and stored

Both methods result in the same authentication state:
- Navbar shows your name and roles
- Idle timeout starts tracking activity
- Token stored in sessionStorage
- SSO session created in Keycloak

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

## Token Management

### Two-Client Architecture

The system uses two Keycloak clients:

1. **portal-frontend** (Public Client)
   - Used by Vue.js frontend for browser-based authentication
   - No client secret required (public client)
   - Supports OAuth2 Authorization Code Flow with PKCE
   - Direct login via Keycloak (credentials never sent to backend)

2. **api** (Confidential Client)
   - Used by FastAPI backend for server-side operations
   - Requires client secret (confidential client)
   - Supports Resource Owner Password Credentials flow
   - Traditional username/password login through backend

### Token Sharing Between Clients

✅ **Tokens work across both clients** because:
- Both clients are in the same `digitaltwins` realm (SSO enabled)
- Backend has `verify_aud: False` (accepts tokens from any client in the realm)
- Token validation checks realm, signature, and expiry

**Example flows:**
- Login via frontend (`portal-frontend`) → Token works for backend API calls ✅
- Login via backend form (`api`) → Token works for API operations ✅
- No re-authentication needed across clients (SSO session shared)

### Token Lifecycle

**Access Token:**
- **Lifespan**: 5 minutes (configurable in Keycloak)
- **Storage**: Browser sessionStorage (`access_token`)
- **Auto-refresh**: Disabled by default
- **Expiry behavior**: APIs return 401, user must re-login

**Refresh Token:**
- **Lifespan**: Up to SSO Session Max (10 hours default)
- **Usage**: Can extend session if auto-refresh is enabled
- **Storage**: Managed by keycloak-js library

**Session Limits:**
- Keycloak SSO Session Max: 10 hours (server-side limit)
- Keycloak SSO Session Idle: 30 minutes server idle timeout
- Frontend Idle Timeout: 30 minutes (client-side, configurable)

### Idle Timeout

Users are automatically logged out after **30 minutes of inactivity**.

**Activity tracking includes:**
- Mouse movements and clicks
- Keyboard input
- Scrolling
- Touch events

**To change timeout duration**, edit `frontend/src/main.ts`:
```typescript
setupIdleTimeout(15); // 15 minutes
setupIdleTimeout(60); // 1 hour
```

### Token Refresh Options

**Current Configuration (Recommended):**
- ❌ No automatic token refresh
- ✅ 30-minute idle timeout
- User re-authenticates when token expires

**Alternative: Auto-Refresh with Session Limit**

Edit `frontend/src/plugins/keycloak.ts` and uncomment "OPTION B" to enable:
- ✅ Automatic token refresh on expiry
- ✅ Maximum session duration (8 hours default)
- Combines convenience with security

### Keycloak Server Configuration

Configure session behavior in **Keycloak Admin Console → Realm Settings → Sessions**:

| Setting | Default | Description |
|---------|---------|-------------|
| SSO Session Idle | 30 minutes | Server-side idle timeout |
| SSO Session Max | 10 hours | Maximum total session duration |
| Access Token Lifespan | 5 minutes | How often token needs validation |
| Refresh Token Max Reuse | 0 | Disables refresh token reuse |

### Token Validation

**Frontend to Backend API calls:**
```typescript
// Token automatically sent via http interceptor
// See: frontend/src/plugins/http.ts
const response = await http.get('/api/some-endpoint');
```

**Backend validation logic:**
```python
# Validates:
# - Token signature (RS256)
# - Token expiry (exp claim)
# - Issuer (Keycloak realm)
# - Audience (accepts any client in realm by default)
# See: backend/app/client/keycloak.py
```

### Production Security Recommendations

1. **Enable Audience Validation** (optional):
   - Add audience mapper in Keycloak for `portal-frontend` client
   - Include `api` in token audience
   - Change backend `verify_aud: False` to `True`

2. **Configure CORS properly**:
   - Add valid redirect URIs in Keycloak
   - Set Web Origins to allowed domains

3. **Use HTTPS in production**:
   - Self-signed certificates cause browser warnings
   - Use proper SSL/TLS certificates

4. **Monitor session durations**:
   - Review Keycloak session logs
   - Adjust timeouts based on user behavior

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

### Token expired / 401 errors
- Access tokens expire after 5 minutes by default
- Re-login to get a new token
- Consider enabling auto-refresh in keycloak.ts (OPTION B)

### Idle timeout too short/long
- Edit `frontend/src/main.ts` and change `setupIdleTimeout(30)` value
- Value is in minutes

### Cross-client token issues
- Ensure both clients (`api` and `portal-frontend`) are in the same realm
- Verify backend has `verify_aud: False` in keycloak.py
- Check Keycloak client configurations

## Key Files

Frontend:
- src/views/login/index.vue - Login page with dual authentication methods
- src/components/AuthNavBar.vue - Navigation bar with user info
- src/store/auth_store.ts - Authentication state management
- src/plugins/keycloak.ts - Keycloak initialization and token management
- src/plugins/http.ts - HTTP interceptor for token injection
- src/main.ts - App initialization with idle timeout setup

Backend:
- app/client/keycloak.py - Keycloak client and token verification
- app/utils/auth.py - Authentication utilities and dependencies
- app/routers/auth.py - Authentication endpoints
- app/main.py - FastAPI application with auth integration

## Support

For Keycloak server issues, contact the devops team.
