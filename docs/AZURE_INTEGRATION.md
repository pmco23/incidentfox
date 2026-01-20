# Azure MCP Server Integration Guide

This guide walks you through setting up Azure MCP Server for IncidentFox, enabling the agent to query Azure resources, Azure Monitor logs, and metrics.

---

## Quick Start Checklist

- [ ] Create Azure Service Principal with proper RBAC roles
- [ ] Store credentials securely
- [ ] Add Azure MCP configuration to team configuration
- [ ] Test MCP server connection
- [ ] Verify agent can query Azure resources

**Estimated time:** 15-20 minutes

---

## Step 1: Create Azure Service Principal

### Prerequisites

```bash
# Install Azure CLI (if not installed)
# macOS:
brew install azure-cli

# Linux:
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# Verify installation
az --version

# Login to Azure
az login

# Set your subscription
az account set --subscription "YOUR_SUBSCRIPTION_NAME_OR_ID"

# Verify
az account show
```

### Create Service Principal

```bash
# Get your subscription ID
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
echo "Subscription ID: $SUBSCRIPTION_ID"

# Create service principal with Reader role
az ad sp create-for-rbac \
  --name "incidentfox-azure-mcp" \
  --role "Reader" \
  --scopes "/subscriptions/$SUBSCRIPTION_ID" \
  --query "{appId:appId, password:password, tenant:tenant}"

# SAVE THE OUTPUT! You'll see something like:
# {
#   "appId": "12345678-1234-1234-1234-123456789abc",      # CLIENT_ID
#   "password": "your-secret-here",                        # CLIENT_SECRET
#   "tenant": "87654321-4321-4321-4321-cba987654321"      # TENANT_ID
# }
```

**Save these values:**
```bash
export AZURE_TENANT_ID="your-tenant-id"
export AZURE_CLIENT_ID="your-client-id"
export AZURE_CLIENT_SECRET="your-client-secret"
export AZURE_SUBSCRIPTION_ID="your-subscription-id"
```

---

## Step 2: Assign Additional RBAC Roles

### For Azure Monitor / Log Analytics

```bash
# Subscription-wide (all workspaces)
az role assignment create \
  --assignee $AZURE_CLIENT_ID \
  --role "Log Analytics Reader" \
  --scope "/subscriptions/$SUBSCRIPTION_ID"
```

### For Azure Monitor Metrics

```bash
az role assignment create \
  --assignee $AZURE_CLIENT_ID \
  --role "Monitoring Reader" \
  --scope "/subscriptions/$SUBSCRIPTION_ID"
```

### For AKS (Optional)

```bash
az role assignment create \
  --assignee $AZURE_CLIENT_ID \
  --role "Azure Kubernetes Service Cluster User Role" \
  --scope "/subscriptions/$SUBSCRIPTION_ID"
```

### Verify Permissions

```bash
# List all role assignments
az role assignment list \
  --assignee $AZURE_CLIENT_ID \
  --query "[].{Role:roleDefinitionName, Scope:scope}" \
  --output table

# Should show:
# Role                                          Scope
# -------------------------------------------   -----------------------------------
# Reader                                        /subscriptions/xxx
# Log Analytics Reader                          /subscriptions/xxx
# Monitoring Reader                             /subscriptions/xxx
```

---

## Step 3: Store Credentials Securely

### Development (Local Environment Variables)

```bash
# Create local env file (DO NOT COMMIT)
cat > ~/.azure-mcp.env <<EOF
export AZURE_TENANT_ID="your-tenant-id"
export AZURE_CLIENT_ID="your-client-id"
export AZURE_CLIENT_SECRET="your-client-secret"
export AZURE_SUBSCRIPTION_ID="your-subscription-id"
EOF

chmod 600 ~/.azure-mcp.env

# Load credentials for testing
source ~/.azure-mcp.env
```

### Production (AWS Secrets Manager)

```bash
aws secretsmanager create-secret \
  --name incidentfox/azure-mcp-credentials \
  --secret-string '{
    "AZURE_TENANT_ID": "your-tenant-id",
    "AZURE_CLIENT_ID": "your-client-id",
    "AZURE_CLIENT_SECRET": "your-client-secret",
    "AZURE_SUBSCRIPTION_ID": "your-subscription-id"
  }' \
  --region us-west-2
```

### Kubernetes Secret

```bash
kubectl create secret generic azure-mcp-creds \
  --from-env-file=~/.azure-mcp.env \
  --namespace=incidentfox
```

---

## Step 4: Add Azure MCP to Team Configuration

### Configuration Example

Add to your team's `node_configurations.config_json`:

```json
{
  "mcp_servers": {
    "azure-mcp": {
      "name": "Azure MCP Server",
      "command": "npx",
      "args": ["-y", "@azure/mcp@latest", "server", "start"],
      "env": {
        "AZURE_TENANT_ID": "${azure_tenant_id}",
        "AZURE_CLIENT_ID": "${azure_client_id}",
        "AZURE_CLIENT_SECRET": "${azure_client_secret}",
        "AZURE_SUBSCRIPTION_ID": "${azure_subscription_id}"
      },
      "enabled": true,
      "config_schema": {
        "azure_tenant_id": {
          "type": "string",
          "required": true,
          "display_name": "Azure Tenant ID",
          "description": "Azure AD tenant ID"
        },
        "azure_client_id": {
          "type": "string",
          "required": true,
          "display_name": "Azure Client ID",
          "description": "Service Principal application (client) ID"
        },
        "azure_client_secret": {
          "type": "secret",
          "required": true,
          "display_name": "Azure Client Secret",
          "description": "Service Principal secret value"
        },
        "azure_subscription_id": {
          "type": "string",
          "required": true,
          "display_name": "Azure Subscription ID",
          "description": "Azure subscription ID"
        }
      },
      "config_values": {
        "azure_tenant_id": "YOUR_TENANT_ID",
        "azure_client_id": "YOUR_CLIENT_ID",
        "azure_client_secret": "YOUR_CLIENT_SECRET",
        "azure_subscription_id": "YOUR_SUBSCRIPTION_ID"
      }
    }
  }
}
```

---

## Step 5: Test Azure MCP Server

### Test 1: Verify MCP Server Starts Locally

```bash
# Load Azure credentials
source ~/.azure-mcp.env

# Start Azure MCP server manually to test
npx -y @azure/mcp@latest server start

# Expected output:
# MCP Server starting...
# Listening on stdio
# Ready to accept requests

# Press Ctrl+C to stop
```

### Test 2: Test Authentication

```bash
# Test login with service principal
az login --service-principal \
  -u $AZURE_CLIENT_ID \
  -p $AZURE_CLIENT_SECRET \
  --tenant $AZURE_TENANT_ID

# Verify access
az account show

# Test listing resources
az resource list --output table

# Log back in as yourself
az logout
az login
```

### Test 3: Verify in IncidentFox

```bash
# Check effective config includes Azure MCP
curl -H "Authorization: Bearer $INCIDENTFOX_TEAM_TOKEN" \
  http://localhost:8080/api/v1/config/me/effective | jq .mcp_servers
```

---

## Troubleshooting

### Issue: "MCP server failed to start"

**Check:**
1. Azure credentials are set correctly
2. Service Principal has proper RBAC roles
3. npx can run Azure MCP package

```bash
# Test manually
npx -y @azure/mcp@latest server start
```

### Issue: "Authentication failed"

**Check:**
1. Credentials are correct (not expired)
2. Service Principal exists and is not disabled

```bash
# Test SP authentication
az login --service-principal \
  -u $AZURE_CLIENT_ID \
  -p $AZURE_CLIENT_SECRET \
  --tenant $AZURE_TENANT_ID
```

### Issue: "Permission denied to query resources"

**Check RBAC roles:**

```bash
# List all role assignments
az role assignment list \
  --assignee $AZURE_CLIENT_ID \
  --output table
```

Required roles:
- Reader (subscription level)
- Log Analytics Reader (for Azure Monitor)
- Monitoring Reader (for metrics)

---

## Security Best Practices

### 1. Least Privilege
- Start with `Reader` role
- Add specific permissions as needed
- Never use `Contributor` or `Owner` for read-only operations

### 2. Credential Management
- Store in secrets manager (AWS Secrets Manager, Azure Key Vault)
- Rotate every 90 days
- Never commit to git
- Never log credentials

### 3. Scope Permissions

```bash
# Better: Scoped to specific resource group
--scope "/subscriptions/xxx/resourceGroups/prod-rg"

# Best: Scoped to specific resource
--scope "/subscriptions/xxx/resourceGroups/prod-rg/providers/Microsoft.OperationalInsights/workspaces/prod-workspace"

# Use subscription-wide only when necessary
--scope "/subscriptions/xxx"
```

### 4. Credential Rotation

```bash
# Reset credentials (rotate secret)
az ad sp credential reset --id $AZURE_CLIENT_ID

# Update secret in AWS Secrets Manager
aws secretsmanager update-secret \
  --secret-id incidentfox/azure-mcp-credentials \
  --secret-string "{\"AZURE_CLIENT_SECRET\":\"new-secret\"}"
```

---

## Example Agent Queries

Once configured, you can ask the agent:

1. **List Azure Resources:**
   ```
   @incidentfox List all my Azure resources
   ```

2. **Query Azure Monitor Logs (KQL):**
   ```
   @incidentfox Query Azure Monitor for errors in production in the last hour
   ```

3. **Check AKS Cluster Health:**
   ```
   @incidentfox Check the health of my AKS clusters
   ```

4. **Analyze Azure Costs:**
   ```
   @incidentfox Show me the top 10 most expensive Azure resources this month
   ```

---

## Reference

### Find Your Values

```bash
# Subscription ID
az account show --query id -o tsv

# Tenant ID
az account show --query tenantId -o tsv

# Service Principal Client ID (if you forgot)
az ad sp list --display-name "incidentfox-azure-mcp" --query "[0].appId" -o tsv

# List all Log Analytics workspaces
az monitor log-analytics workspace list \
  --query "[].{Name:name, ResourceGroup:resourceGroup, WorkspaceId:customerId}" \
  --output table
```

### Common Resource ID Formats

```bash
# Subscription
/subscriptions/{subscription-id}

# Resource Group
/subscriptions/{subscription-id}/resourceGroups/{rg-name}

# Log Analytics Workspace
/subscriptions/{subscription-id}/resourceGroups/{rg-name}/providers/Microsoft.OperationalInsights/workspaces/{workspace-name}

# AKS Cluster
/subscriptions/{subscription-id}/resourceGroups/{rg-name}/providers/Microsoft.ContainerService/managedClusters/{cluster-name}
```
