# GitHub Actions Workflows

## Security & Quality

| Workflow | Trigger | Description |
|----------|---------|-------------|
| **lint.yml** | Push/PR to main | Runs Ruff + Black, auto-commits fixes to PRs |
| **gitleaks.yml** | Push/PR | Scans for secrets and credentials |
| **trivy.yml** | Push/PR | Security vulnerability scanning |

## Local Development

These workflows run automatically on PRs. For local checks:

```bash
# Lint
pip install ruff black
ruff check . --fix
black .

# Secret scanning
brew install gitleaks  # or your package manager
gitleaks detect

# Security scan
brew install trivy
trivy fs .
```

## Adding Your Own Deployment

For production deployments, you'll need to add your own CI/CD workflows. Example approach:

1. Create `.github/workflows/deploy.yml`
2. Configure secrets for your cloud provider (AWS, GCP, Azure)
3. Build and push Docker images
4. Deploy to your Kubernetes cluster

See [local/README.md](../../local/README.md) for local development setup.
