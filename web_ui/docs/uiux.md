## IncidentFox Web UI — UX Audit + Rebuild Plan (Enterprise)

### Goals / Principles
- **Auth gate first**: no sidebar, no pages, no identity chrome until the user is authenticated.
- **Role-driven navigation**: `role=admin` sees admin console pages; `role=team` sees team-only pages.
- **Enterprise-safe auth**: **no tokens in localStorage** by default; use **httpOnly cookie session**.
- **Clear separation**:
  - Authentication/session
  - Product functionality (team config / admin console)
  - Preferences (theme/language) — can be local-only initially

---

## Current UX Issues (Audit)

### Authentication & first-run
- **Unauthenticated shell renders**: the app shows sidebar + identity chrome even when not signed in.
- **Token entry is misplaced**: token entry inside “RBAC/Settings” is confusing and insecure.
- **Home page is a login prompt**: unnecessary page that exists only to direct users to settings.

### Navigation / structure
- **Information architecture is unclear**: “demo” concepts leak into the product (incidents/learning/integrations).
- **Role gating is inconsistent**: users can click into pages they shouldn’t see and then hit confusing states.

### Identity + account controls
- **Bottom-left user area isn’t a real account menu**: should be actionable (logout, switch token, preferences).
- **Identity isn’t always real**: must always come from backend (`/api/v1/auth/me`) once signed in.

### Settings & preferences
- **Governance mixed with preferences**: theme/language aren’t RBAC.
- **Preference persistence**: acceptable to use localStorage initially, but must be isolated (and later server-side).

### Enterprise readiness
- **Token handling**: long-lived bearer tokens in localStorage is not acceptable for enterprise default posture.
- **Auditing**: admin actions should show actor/timestamps (later phase).

---

## Target UX (Fresh Rebuild)

### 1) Auth gate (full-screen)
- **Unauthenticated view**: show a **Sign In modal/screen only**.
- No sidebar. No navigation. No page content.

**Sign In screen contents**
- Token input (admin token / team token / OIDC JWT)
- Primary action: **Continue**
- Error handling: invalid/expired token; show actionable help text
- Optional: “remember me” is not required in phase 1 (session cookie is fine)

### 2) App shell after identity
- Once authenticated (identity loaded):
  - render sidebar + top-level layout
  - route `/` to a role landing:
    - admin → `/admin`
    - team → `/configuration`

### 3) Account menu
Bottom-left becomes an **Account menu** (clickable):
- Identity summary (role/org/team/auth_kind)
- Actions:
  - **Switch token** (opens Sign In)
  - **Log out**
  - Preferences:
    - theme toggle (dark/light)
    - language selector placeholder (phase 1 local-only)

### 4) Role-based navigation
- **Admin**
  - Org Tree
  - Token Management
  - (later) Audit Log, Config Preview
- **Team**
  - Team Configuration
  - Explainability (can be a tab/section in Team Configuration)

---

## Backend Endpoint Mapping (UI → Service)

### Authentication / identity
- **Canonical**: `GET /api/v1/auth/me`
- **UI proxy**: `GET /api/identity` → upstream `GET /api/v1/auth/me`

### Session (enterprise-safe; web-ui owned)
- `POST /api/session/login`:
  - body: `{ token: string }`
  - sets `httpOnly` cookie `incidentfox_session_token`
- `POST /api/session/logout`:
  - clears cookie

### Team config (team role)
- `GET /api/v1/config/me/effective`
- `GET /api/v1/config/me/raw`
- `PUT /api/v1/config/me` (deep-merge semantics)

### Admin org / tokens (admin role)
- `GET /api/v1/admin/orgs/{org_id}/nodes`
- `GET /api/v1/admin/orgs/{org_id}/teams/{team_node_id}/tokens`
- `POST /api/v1/admin/orgs/{org_id}/teams/{team_node_id}/tokens`
- `POST /api/v1/admin/orgs/{org_id}/teams/{team_node_id}/tokens/{token_id}/revoke`

### Admin “act as team” / preview (recommended; phase 2)
- `GET /api/v1/admin/orgs/{org_id}/nodes/{node_id}/effective`
- `GET /api/v1/admin/orgs/{org_id}/nodes/{node_id}/raw`

---

## Implementation Plan

### Phase 1 (now)
- Implement auth gate: show Sign In until identity is present
- Move token entry to Sign In; remove token entry from Settings/RBAC page
- Implement session cookie login/logout
- Implement role-based sidebar
- Implement account menu (logout, switch token, theme toggle, language placeholder)
- Remove demo-only hardcoded pages from nav (already stubbed) and stop loading any demo datasets

### Phase 2
- Add admin preview endpoints on config service
- Add “act as team” UX for admins (team picker + preview)
- Audit log UI
- Replace local-only prefs with backend user profile (optional)


