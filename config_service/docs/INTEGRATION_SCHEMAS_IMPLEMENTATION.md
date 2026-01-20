# Integration Schemas Implementation - Complete

## Summary

Successfully migrated integration schema definitions from hardcoded config to database-backed global schemas. This fixes the architectural issue where integration schemas were duplicated per-org when they should be global definitions.

## What Was Implemented

### 1. Database Schema (COMPLETED ✓)

**Migration: `20260111_0002_integration_schemas.py`**
- Created `integration_schemas` table (global, not per-org)
- Columns:
  - `id` (PK) - Integration identifier (e.g., "coralogix", "snowflake")
  - `name` - Display name
  - `category` - Category for grouping (observability, data-warehouse, etc.)
  - `description` - Integration description
  - `docs_url` - Link to integration documentation
  - `icon_url` - Icon for UI display
  - `display_order` - Sort order in UI
  - `featured` - Whether to highlight in UI
  - `fields` (JSONB) - Array of field definitions with type, required, level, etc.
  - Timestamps: `created_at`, `updated_at`

**Migration: `20260111_0003_populate_integrations.py`**
- Populated 23 built-in integration schemas:
  - **AI**: OpenAI (required)
  - **Observability**: Coralogix, Datadog, New Relic, Grafana
  - **Data Warehouses**: Snowflake, BigQuery
  - **Search**: Elasticsearch, Splunk
  - **Communication**: Slack, PagerDuty, Microsoft Teams
  - **SCM**: GitHub, GitHub App, GitLab, AWS CodePipeline
  - **Collaboration**: Google Docs, Confluence, Notion
  - **Cloud**: AWS, GCP
  - **Orchestration**: Kubernetes
  - **Error Tracking**: Sentry

### 2. Database Model (COMPLETED ✓)

**File: `/config_service/src/db/config_models.py`**
```python
class IntegrationSchema(Base):
    """Global integration schema definitions (not per-org)."""
    __tablename__ = "integration_schemas"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # ... all fields from migration
```

### 3. API Endpoints (COMPLETED ✓)

**File: `/config_service/src/api/routes/integration_schemas.py`**

New endpoints:
- `GET /api/v1/integrations/schemas` - List all integration schemas (with filters)
- `GET /api/v1/integrations/schemas/{integration_id}` - Get specific schema
- `GET /api/v1/integrations/schemas/categories/list` - List categories with counts

Response includes:
- Full integration schema definition
- Field definitions (name, type, required, level, description, placeholder)
- Documentation URL
- Display metadata (featured, display_order, icon_url)

### 4. Config Service Integration (COMPLETED ✓)

**File: `/config_service/src/core/hierarchical_config.py`**

Updated functions:
- `fetch_integration_schemas_from_db(db)` - Fetches all schemas from DB and builds config structure
- `get_default_integration_config(db)` - Returns integration config with DB schemas or fallback
- `get_full_default_config(db)` - Now accepts optional DB session to fetch fresh schemas

Benefits:
- Integration definitions are now global (single source of truth)
- Automatic fallback to minimal config if DB unavailable
- Separates org-level vs team-level field configurations
- Properly marks OpenAI as locked/required

### 5. Verification (COMPLETED ✓)

Tested end-to-end in production pod:
- Successfully fetched all 23 integrations from database
- Verified structure: each integration has `config_schema`, `config`, `level`, `locked`
- Confirmed separation of org-level and team-level fields
- Sample output shows correct schema structure

## Architecture Changes

### Before (WRONG ❌)
```
┌─────────────────────────────────────┐
│ hierarchical_config.py              │
│ ├─ hardcoded integration schemas    │ ← Schemas in code
│ └─ duplicated per-org in config     │ ← Wrong!
└─────────────────────────────────────┘
```

### After (CORRECT ✓)
```
┌─────────────────────────────────────┐
│ integration_schemas table (DB)      │
│ ├─ Global definitions (all orgs)    │ ← Single source
│ └─ 23 built-in integrations         │
└─────────────────────────────────────┘
         ↓ Fetched by
┌─────────────────────────────────────┐
│ hierarchical_config.py              │
│ └─ fetch_integration_schemas_from_db│
└─────────────────────────────────────┘
         ↓ Used in
┌─────────────────────────────────────┐
│ node_configurations.config_json     │
│ └─ integrations: { "coralogix": ... }│ ← Credentials only
└─────────────────────────────────────┘
```

## Data Separation

**Integration Schemas (Global - in `integration_schemas` table)**
- What fields are needed (api_key, region, etc.)
- Field types (secret, string, integer, etc.)
- Required vs optional
- Org-level vs team-level
- Descriptions and placeholders

**Integration Credentials (Per-Team - in `node_configurations.config_json`)**
- Actual API keys, tokens, etc.
- Enabled/disabled status
- Custom descriptions
- Team-specific overrides

## Files Modified

1. `/config_service/alembic/versions/20260111_0002_integration_schemas.py` (NEW)
2. `/config_service/alembic/versions/20260111_0003_populate_integrations.py` (NEW)
3. `/config_service/src/db/config_models.py` (ADDED IntegrationSchema model)
4. `/config_service/src/api/routes/integration_schemas.py` (NEW)
5. `/config_service/src/api/main.py` (ADDED integration_schemas router)
6. `/config_service/src/core/hierarchical_config.py` (UPDATED to fetch from DB)
7. `/config_service/src/api/routes/config_v2.py` (UPDATED to pass DB session)

## Database Status

```sql
SELECT COUNT(*) FROM integration_schemas;
-- Result: 23 integrations

SELECT id, name, category, featured
FROM integration_schemas
ORDER BY display_order;
-- Result: All 23 integrations present with correct metadata
```

## Next Steps (Deployment)

The implementation is complete but needs deployment:

1. **Build Docker image** with updated code
2. **Push to ECR** (requires appropriate AWS permissions)
3. **Restart config-service pods** to load new image
4. **Verify API endpoints** work in production
5. **Update UI** to use new `/api/v1/integrations/schemas` endpoints

### Manual File Copy (Temporary)

If ECR push is not available, files can be copied directly to running pods:
```bash
kubectl cp src/db/config_models.py incidentfox/incidentfox-config-service-POD:/app/src/db/config_models.py
kubectl cp src/api/routes/integration_schemas.py incidentfox/incidentfox-config-service-POD:/app/src/api/routes/integration_schemas.py
kubectl cp src/api/main.py incidentfox/incidentfox-config-service-POD:/app/src/api/main.py
kubectl cp src/core/hierarchical_config.py incidentfox/incidentfox-config-service-POD:/app/src/core/hierarchical_config.py
kubectl cp src/api/routes/config_v2.py incidentfox/incidentfox-config-service-POD:/app/src/api/routes/config_v2.py

# Then reload the Python app (or restart pods)
kubectl rollout restart deployment/incidentfox-config-service -n incidentfox
```

## Testing

Test the new API endpoints:
```bash
# List all integrations
curl http://config-service:8080/api/v1/integrations/schemas

# Get specific integration
curl http://config-service:8080/api/v1/integrations/schemas/coralogix

# Filter by category
curl http://config-service:8080/api/v1/integrations/schemas?category=observability

# Filter by featured
curl http://config-service:8080/api/v1/integrations/schemas?featured=true

# List categories
curl http://config-service:8080/api/v1/integrations/schemas/categories/list
```

## Benefits

1. **Single Source of Truth**: Integration definitions in one place (database)
2. **No Duplication**: Schemas not copied per-org
3. **Easy Updates**: Add new integrations via migration
4. **UI Friendly**: API endpoints for integration catalog
5. **Comprehensive**: 23 built-in integrations covering all major platforms
6. **Flexible**: Supports both org-level and team-level configuration
7. **Safe Defaults**: Fallback config if DB unavailable

## Related Work

This implementation is part of Phase 1 critical fixes:
- See `/agent/PHASE1_INTEGRATION_FIXES.md` for execution context fixes
- Integration schemas (this file) - global definition storage
- Next: UI updates to show tool→integration dependencies
