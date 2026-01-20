# Web UI - Backend-for-Frontend Pattern

API routes in `src/app/api/` act as a Backend-for-Frontend layer.

---

## Why BFF?

**Problem**: Frontend can't directly call backend services (CORS, auth complexity)

**Solution**: Next.js API routes proxy requests with:
- Authentication handling
- Request/response transformation
- Error handling
- CORS management

---

## Example: Agent Runs API

```typescript
// src/app/api/team/runs/route.ts

export async function GET(request: Request) {
  // 1. Get auth token from cookie
  const token = cookies().get('incidentfox_session_token')?.value

  // 2. Proxy to Config Service
  const response = await fetch(
    `${CONFIG_SERVICE_URL}/api/v1/agent-runs`,
    {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    }
  )

  // 3. Return to frontend
  return Response.json(await response.json())
}
```

---

## BFF Routes

| Frontend Calls | BFF Route | Backend Service |
|----------------|-----------|-----------------|
| `GET /api/team/config` | `src/app/api/team/config/route.ts` | Config Service |
| `GET /api/team/stats` | `src/app/api/team/stats/route.ts` | Config Service |
| `GET /api/team/runs` | `src/app/api/team/runs/route.ts` | Config Service |
| `GET /api/team/knowledge/tree` | `src/app/api/team/knowledge/tree/route.ts` | RAPTOR KB API |
| `POST /api/team/templates` | `src/app/api/team/templates/route.ts` | Config Service |

---

## Authentication Flow

```
Frontend → BFF → Backend
   ↓        ↓        ↓
Cookie → Extract → Bearer Token
```

BFF extracts session token from cookie and adds `Authorization` header for backend.

---

## Error Handling

```typescript
try {
  const response = await fetch(backend_url, ...)

  if (!response.ok) {
    return Response.json(
      { error: 'Backend error' },
      { status: response.status }
    )
  }

  return Response.json(await response.json())
} catch (error) {
  return Response.json(
    { error: 'Network error' },
    { status: 500 }
  )
}
```

---

## Related Documentation

- `/web_ui/docs/README.md` - Web UI overview
