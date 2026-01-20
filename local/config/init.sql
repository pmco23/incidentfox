-- ═══════════════════════════════════════════════════════════════════════════════
-- IncidentFox Local Development - Database Initialization
-- ═══════════════════════════════════════════════════════════════════════════════
-- This script initializes the database for local development.
-- Based on config_service alembic migration: 20260111_initial
-- ═══════════════════════════════════════════════════════════════════════════════

-- ═══════════════════════════════════════════════════════════════════════════════
-- SCHEMA CREATION
-- ═══════════════════════════════════════════════════════════════════════════════

-- Core org/team hierarchy
CREATE TABLE org_nodes (
    org_id VARCHAR(64) NOT NULL,
    node_id VARCHAR(128) NOT NULL,
    node_type VARCHAR(32) NOT NULL,
    name VARCHAR(256) NOT NULL,
    parent_id VARCHAR(128),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    PRIMARY KEY (org_id, node_id)
);
CREATE INDEX ix_org_nodes_org_id ON org_nodes(org_id);
CREATE INDEX ix_org_nodes_parent_id ON org_nodes(parent_id);

-- Node configurations (main config storage)
CREATE TABLE node_configs (
    org_id VARCHAR(64) NOT NULL,
    node_id VARCHAR(128) NOT NULL,
    config_json JSONB NOT NULL DEFAULT '{}',
    version INTEGER NOT NULL DEFAULT 1,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_by VARCHAR(128),
    PRIMARY KEY (org_id, node_id),
    FOREIGN KEY (org_id, node_id) REFERENCES org_nodes(org_id, node_id) ON DELETE CASCADE
);
CREATE INDEX ix_node_configs_org_id ON node_configs(org_id);

-- Team tokens (authentication)
CREATE TABLE team_tokens (
    org_id VARCHAR(64) NOT NULL,
    team_node_id VARCHAR(128) NOT NULL,
    token_id VARCHAR(128) NOT NULL,
    token_hash TEXT NOT NULL,
    issued_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMP WITH TIME ZONE,
    issued_by VARCHAR(128),
    expires_at TIMESTAMP WITH TIME ZONE,
    last_used_at TIMESTAMP WITH TIME ZONE,
    permissions JSONB NOT NULL DEFAULT '["config:read", "config:write", "agent:invoke"]',
    label VARCHAR(256),
    PRIMARY KEY (org_id, team_node_id, token_id),
    FOREIGN KEY (org_id, team_node_id) REFERENCES org_nodes(org_id, node_id) ON DELETE CASCADE
);
CREATE INDEX ix_team_tokens_org_team ON team_tokens(org_id, team_node_id);
CREATE INDEX ix_team_tokens_token_hash ON team_tokens(token_hash);

-- Org admin tokens
CREATE TABLE org_admin_tokens (
    token_id VARCHAR(64) NOT NULL,
    org_id VARCHAR(64) NOT NULL,
    token_hash TEXT NOT NULL,
    name VARCHAR(256),
    created_by VARCHAR(256),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (token_id)
);
CREATE INDEX ix_org_admin_tokens_org_id ON org_admin_tokens(org_id);
CREATE INDEX ix_org_admin_tokens_token_hash ON org_admin_tokens(token_hash);

-- Token audit log
CREATE TABLE token_audit (
    id BIGSERIAL PRIMARY KEY,
    token_id VARCHAR(64) NOT NULL,
    org_id VARCHAR(64) NOT NULL,
    team_node_id VARCHAR(128),
    event_type VARCHAR(32) NOT NULL,
    ip_address VARCHAR(64),
    user_agent TEXT,
    endpoint VARCHAR(256),
    success BOOLEAN NOT NULL,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_token_audit_token_id ON token_audit(token_id);
CREATE INDEX ix_token_audit_org_id ON token_audit(org_id);
CREATE INDEX ix_token_audit_created_at ON token_audit(created_at);

-- Config audit log
CREATE TABLE node_config_audit (
    org_id VARCHAR(64) NOT NULL,
    node_id VARCHAR(128) NOT NULL,
    changed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    changed_by VARCHAR(256),
    old_config JSONB,
    new_config JSONB,
    change_summary TEXT
);
CREATE INDEX ix_node_config_audit_org_node ON node_config_audit(org_id, node_id);
CREATE INDEX ix_node_config_audit_changed_at ON node_config_audit(changed_at);

-- Agent runs (execution history)
CREATE TABLE agent_runs (
    id VARCHAR(64) PRIMARY KEY,
    org_id VARCHAR(64) NOT NULL,
    team_node_id VARCHAR(128),
    correlation_id VARCHAR(64),
    trigger_source VARCHAR(32) NOT NULL,
    trigger_actor VARCHAR(128),
    trigger_message TEXT,
    trigger_channel_id VARCHAR(64),
    agent_name VARCHAR(64) NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(32) NOT NULL,
    tool_calls_count INTEGER,
    output_summary TEXT,
    output_json JSONB,
    error_message TEXT,
    confidence INTEGER,
    duration_seconds FLOAT,
    extra_metadata JSONB
);
CREATE INDEX ix_agent_runs_org_id ON agent_runs(org_id);
CREATE INDEX ix_agent_runs_team_node_id ON agent_runs(team_node_id);
CREATE INDEX ix_agent_runs_started_at ON agent_runs(started_at);
CREATE INDEX ix_agent_runs_status ON agent_runs(status);

-- Agent sessions
CREATE TABLE agent_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    investigation_id VARCHAR(256) NOT NULL UNIQUE,
    sdk_session_id VARCHAR(256),
    session_data TEXT,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    last_accessed_at TIMESTAMP WITH TIME ZONE,
    message_count INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER,
    total_cost_usd NUMERIC(10, 6),
    session_metadata JSONB
);
CREATE INDEX ix_agent_sessions_investigation_id ON agent_sessions(investigation_id);
CREATE INDEX ix_agent_sessions_status ON agent_sessions(status);

-- Security policies
CREATE TABLE security_policies (
    org_id VARCHAR(64) PRIMARY KEY,
    require_mfa BOOLEAN NOT NULL DEFAULT FALSE,
    session_timeout_minutes INTEGER,
    allowed_ip_ranges JSONB,
    token_expiry_days INTEGER,
    require_approval_for_config_changes BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_by VARCHAR(256)
);

-- SSO configs
CREATE TABLE sso_configs (
    org_id VARCHAR(64) PRIMARY KEY,
    provider VARCHAR(32) NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    saml_metadata_url TEXT,
    saml_entity_id VARCHAR(256),
    oidc_client_id VARCHAR(256),
    oidc_client_secret TEXT,
    oidc_discovery_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Org settings (telemetry, etc.)
CREATE TABLE org_settings (
    org_id VARCHAR(64) PRIMARY KEY,
    telemetry_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    usage_analytics_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    error_reporting_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    feature_flags JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_by VARCHAR(128)
);

-- Knowledge documents
CREATE TABLE knowledge_documents (
    org_id VARCHAR(64) NOT NULL,
    team_node_id VARCHAR(128) NOT NULL,
    doc_id VARCHAR(256) NOT NULL,
    title VARCHAR(512),
    content TEXT NOT NULL,
    source_type VARCHAR(64),
    source_id VARCHAR(256),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (org_id, team_node_id, doc_id),
    FOREIGN KEY (org_id, team_node_id) REFERENCES org_nodes(org_id, node_id) ON DELETE CASCADE
);

-- Knowledge edges (graph)
CREATE TABLE knowledge_edges (
    org_id VARCHAR(64) NOT NULL,
    team_node_id VARCHAR(128) NOT NULL,
    entity VARCHAR(256) NOT NULL,
    relationship VARCHAR(64) NOT NULL,
    target VARCHAR(256) NOT NULL,
    source TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (org_id, team_node_id, entity, relationship, target),
    FOREIGN KEY (org_id, team_node_id) REFERENCES org_nodes(org_id, node_id) ON DELETE CASCADE
);

-- Pending config changes (approval workflow)
CREATE TABLE pending_config_changes (
    change_id VARCHAR(64) PRIMARY KEY,
    org_id VARCHAR(64) NOT NULL,
    node_id VARCHAR(128) NOT NULL,
    requested_config JSONB NOT NULL,
    change_diff JSONB,
    requested_by VARCHAR(128) NOT NULL,
    requested_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    justification TEXT,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    reviewed_by VARCHAR(128),
    reviewed_at TIMESTAMP WITH TIME ZONE,
    review_comment TEXT
);
CREATE INDEX ix_pending_config_changes_org_node ON pending_config_changes(org_id, node_id);
CREATE INDEX ix_pending_config_changes_status ON pending_config_changes(status);

-- Templates
CREATE TABLE templates (
    template_id VARCHAR(64) PRIMARY KEY,
    org_id VARCHAR(64) NOT NULL,
    created_by_team_id VARCHAR(128),
    name VARCHAR(256) NOT NULL,
    description TEXT,
    category VARCHAR(64),
    tags JSONB NOT NULL DEFAULT '[]',
    template_config JSONB NOT NULL,
    is_public BOOLEAN NOT NULL DEFAULT FALSE,
    is_featured BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_by VARCHAR(128)
);
CREATE INDEX ix_templates_org_id ON templates(org_id);
CREATE INDEX ix_templates_category ON templates(category);
CREATE INDEX ix_templates_is_public ON templates(is_public);

-- Impersonation JTIs
CREATE TABLE impersonation_jtis (
    jti VARCHAR(64) PRIMARY KEY,
    org_id VARCHAR(64) NOT NULL,
    team_node_id VARCHAR(128) NOT NULL,
    subject VARCHAR(256),
    email VARCHAR(256),
    issued_at TIMESTAMP WITH TIME ZONE NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    FOREIGN KEY (org_id, team_node_id) REFERENCES org_nodes(org_id, node_id) ON DELETE CASCADE
);
CREATE INDEX ix_impersonation_jtis_org_team ON impersonation_jtis(org_id, team_node_id);
CREATE INDEX ix_impersonation_jtis_expires_at ON impersonation_jtis(expires_at);

-- ═══════════════════════════════════════════════════════════════════════════════
-- SEED DATA FOR LOCAL DEVELOPMENT
-- ═══════════════════════════════════════════════════════════════════════════════

-- Create local organization with org and default team
INSERT INTO org_nodes (org_id, node_id, node_type, name, parent_id) VALUES
    ('local', 'root', 'org', 'Local Development', NULL),
    ('local', 'default', 'team', 'Default Team', 'root');

-- Create org-level config (inherited by all teams)
INSERT INTO node_configs (org_id, node_id, config_json, version, updated_by) VALUES
    ('local', 'root', '{
        "agents": {
            "planner": {
                "enabled": true,
                "model": {"name": "gpt-4o-mini", "temperature": 0.2}
            },
            "investigation": {
                "enabled": true,
                "model": {"name": "gpt-4o-mini", "temperature": 0.2}
            },
            "k8s_agent": {
                "enabled": true,
                "model": {"name": "gpt-4o-mini", "temperature": 0.1}
            },
            "aws_agent": {
                "enabled": true,
                "model": {"name": "gpt-4o-mini", "temperature": 0.1}
            },
            "metrics_agent": {
                "enabled": true,
                "model": {"name": "gpt-4o-mini", "temperature": 0.1}
            },
            "coding_agent": {
                "enabled": true,
                "model": {"name": "gpt-4o-mini", "temperature": 0.2}
            },
            "ci_agent": {
                "enabled": true,
                "model": {"name": "gpt-4o-mini", "temperature": 0.1}
            }
        },
        "feature_flags": {
            "multi_agent": true,
            "streaming_output": true,
            "tool_approval": false
        }
    }', 1, 'init.sql');

-- Create team-level config (overrides org defaults)
INSERT INTO node_configs (org_id, node_id, config_json, version, updated_by) VALUES
    ('local', 'default', '{
        "team_name": "Default Team",
        "environment": {
            "platform": "local",
            "cloud": "none"
        },
        "routing": {
            "slack_channels": [],
            "github_repos": []
        }
    }', 1, 'init.sql');

-- Create org settings (telemetry disabled for local)
INSERT INTO org_settings (org_id, telemetry_enabled, usage_analytics_enabled, error_reporting_enabled, feature_flags, updated_by) VALUES
    ('local', false, false, false, '{}', 'init.sql');

-- ═══════════════════════════════════════════════════════════════════════════════
-- NOTE: Team token will be generated by 'make seed' using config_service script
-- ═══════════════════════════════════════════════════════════════════════════════
