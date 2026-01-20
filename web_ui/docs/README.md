# Web UI - Overview

Next.js 16.0.7 frontend for IncidentFox.

---

## Structure

```
web_ui/
├── src/
│   ├── app/                    # Next.js App Router
│   │   ├── api/                # API routes (Backend-for-Frontend)
│   │   ├── team/               # Team dashboard pages
│   │   │   ├── agents/         # Agent topology editor
│   │   │   ├── tools/          # Tools & MCPs configuration
│   │   │   ├── knowledge/      # RAPTOR KB explorer
│   │   │   └── remediations/   # Remediation approvals
│   │   └── page.tsx            # Dashboard home
│   ├── components/             # React components
│   └── lib/                    # Utilities
└── public/                     # Static assets
```

---

## Key Pages

| Page | Path | Purpose |
|------|------|---------|
| Dashboard | `/team` | Stats, agent runs, remediations |
| Agent Topology | `/team/agents` | Visual agent editor (React Flow) |
| Tools & MCPs | `/team/tools` | Configure integrations & MCPs |
| Knowledge Explorer | `/team/knowledge` | Browse RAPTOR KB tree |
| Remediations | `/team/remediations` | Approve proposed actions |

---

## Backend-for-Frontend (BFF)

API routes in `src/app/api/` proxy to backend services:

```
GET /api/team/config        → Config Service
GET /api/team/stats         → Config Service
GET /api/team/runs          → Config Service
GET /api/team/knowledge/*   → RAPTOR KB API
```

See: `/web_ui/docs/BFF_PATTERN.md`

---

## Authentication

Session token stored in cookie: `incidentfox_session_token`

```typescript
// src/lib/auth.ts
export async function getIdentity() {
  const token = cookies().get('incidentfox_session_token')?.value
  // ...
}
```

---

## State Management

Redux Toolkit for global state:
- Agent topology state
- Integration configurations
- Knowledge base tree state

---

## Styling

Tailwind CSS 4.0.10 for styling.

---

## Development

```bash
cd web_ui
npm install
npm run dev  # http://localhost:3000
```

---

## Related Documentation

- `/web_ui/docs/BFF_PATTERN.md` - API routes pattern
- `/web_ui/docs/DEPLOYMENT.md` - Build & deploy
- `/web_ui/docs/uiux.md` - UI/UX notes
