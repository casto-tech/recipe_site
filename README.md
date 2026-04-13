# The Recipe Book

A single-page recipe website built with Django 5, HTMX, Alpine.js, and Tailwind CSS. Browse and search a personal recipe collection with real-time filtering and a card-based detail view. Deployed on Azure Container Apps with PostgreSQL and Azure Blob Storage.

---

## Table of Contents

- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Local Setup](#local-setup)
- [Running Tests](#running-tests)
- [Managing Recipes](#managing-recipes-local-admin)
- [Common Development Commands](#common-development-commands)
- [Database Management](#database-management)
- [Deployment](#deployment)
- [Azure Infrastructure Setup](#azure-infrastructure-setup)
- [GitHub Actions Secrets](#github-actions-secrets)
- [Environment Variables Reference](#environment-variables-reference)
- [Security Notes](#security-notes)
- [Troubleshooting](#troubleshooting)

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Django 5, Python 3.12 |
| Database | PostgreSQL 16 |
| Frontend | HTMX, Alpine.js, Tailwind CSS (CDN Play) |
| Container | Docker (multi-stage, non-root) |
| Hosting | Azure Container Apps |
| Image registry | Azure Container Registry (ACR) |
| Media storage | Azure Blob Storage |
| Static files | WhiteNoise (in-container, compressed + hashed) |
| CI/CD | GitHub Actions |

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker Engine + Docker Compose)
- Python 3.12 (for running management commands outside Docker)
- Git
- Azure CLI (`az`) — for infrastructure management only

---

## Local Setup

### 1. Clone the repository

```bash
git clone https://github.com/casto-tech/recipe_site.git
cd recipe_site
```

### 2. Create and configure your environment file

```bash
cp .env.example .env
```

Open `.env` and replace the placeholder values with real secrets:

```bash
# Generate a Django secret key:
python -c "import secrets; print(secrets.token_urlsafe(64))"

# Generate a database password:
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Set the generated values for `DJANGO_SECRET_KEY` and `DB_PASSWORD` in `.env`.

### 3. Build and start the application

```bash
docker-compose up --build -d
```

This starts two services:
- `db` — PostgreSQL 16 (internal network only, not exposed to host)
- `web` — Django dev server on port 8000 (runs migrations automatically on start)

### 4. Load sample data (optional)

```bash
docker-compose exec web python manage.py load_sample_recipes
```

Loads 8 sample recipes with tags (Italian, Mexican, American, Vegetarian, Dessert, Asian, Quick, Comfort Food). Safe to run multiple times — uses `get_or_create`.

### 5. Open the site

Visit [http://localhost:8000](http://localhost:8000)

---

## Running Tests

Run the full test suite inside the Docker container (uses the running `db` service):

```bash
docker-compose exec web pytest tests/ -v
```

Run with coverage report:

```bash
docker-compose exec web pytest tests/ --cov=recipes --cov-report=term-missing -v
```

Run a specific test file:

```bash
docker-compose exec web pytest tests/test_views.py -v
docker-compose exec web pytest tests/test_security.py -v
```

Run linting and formatting checks:

```bash
docker-compose exec web flake8 recipes/ config/ --max-line-length=120 --exclude=migrations
docker-compose exec web black --check recipes/ config/ tests/
```

Auto-format code:

```bash
docker-compose exec web black recipes/ config/ tests/
```

> The test suite requires **≥80% code coverage** to pass. The CI pipeline enforces this gate.

---

## Managing Recipes (Local Admin)

> **The admin interface is only available locally.** It does not exist in production — `django.contrib.admin` is removed from `INSTALLED_APPS` entirely in the production image and all `/management/` paths return HTTP 404.

### Create a superuser

```bash
docker-compose exec web python manage.py createsuperuser
```

### Access the admin

Open [http://localhost:8000/management/](http://localhost:8000/management/) and log in.

### What you can manage

- **Recipes** — title, slug (auto-generated from title), image upload, image URL fallback, ingredients, directions, tags
- **Tags** — name and auto-generated slug

### Ingredient format

Enter one ingredient per line:

```
2 cups flour
1 tsp baking powder
3 large eggs
100g unsalted butter, softened
```

### Directions format

Enter one step per line — displayed as a numbered list on the site:

```
Preheat oven to 180°C.
Mix dry ingredients in a large bowl.
Add wet ingredients and stir until just combined.
Pour batter into greased tin and bake 30 minutes.
```

### Recipe images

Two options:
1. **Upload an image** — stored in Azure Blob Storage (production) or the local `media/` directory (dev). Uploaded images take priority.
2. **Image URL** — a fallback URL for external images (e.g. Picsum for sample data). Only used if no uploaded image exists.

---

## Common Development Commands

### Start / stop services

```bash
# Start in background
docker-compose up -d

# Start with logs visible
docker-compose up

# Stop services (keep volumes)
docker-compose down

# Stop and delete all data (volumes)
docker-compose down -v
```

### Rebuild the image (after Dockerfile or requirements changes)

```bash
docker-compose up --build -d
```

### View logs

```bash
# All services
docker-compose logs -f

# Web service only
docker-compose logs -f web

# Database only
docker-compose logs -f db
```

### Open a Django shell

```bash
docker-compose exec web python manage.py shell
```

### Open a database shell

```bash
docker-compose exec db psql -U recipes_user -d recipes
```

### Run any management command

```bash
docker-compose exec web python manage.py <command>
```

---

## Database Management

### Run migrations

Migrations run automatically on container startup. To run them manually:

```bash
docker-compose exec web python manage.py migrate
```

### Create a new migration after model changes

```bash
docker-compose exec web python manage.py makemigrations
docker-compose exec web python manage.py migrate
```

### Show migration status

```bash
docker-compose exec web python manage.py showmigrations
```

### Reset the database (local dev only)

```bash
# Stop services and delete volumes
docker-compose down -v

# Restart fresh — migrations run automatically
docker-compose up -d

# Reload sample data
docker-compose exec web python manage.py load_sample_recipes
```

### Create a database backup (local)

```bash
docker-compose exec db pg_dump -U recipes_user recipes > backup_$(date +%Y%m%d_%H%M%S).sql
```

### Restore a database backup (local)

```bash
docker-compose exec -T db psql -U recipes_user recipes < backup_YYYYMMDD_HHMMSS.sql
```

---

## Deployment

Deployment is fully automated via GitHub Actions on every push to `main`. No manual steps are required after the initial Azure infrastructure is set up.

### Pipeline stages

```
git push main
    │
    ▼
CI — Tests & Linting (flake8, black, pytest ≥80% coverage)
    │ must pass
    ▼
Security — SAST, CVE & Image Scan (pip-audit, bandit, CodeQL, Trivy)
    │ must pass
    ▼
Deploy — Build, Push & Deploy to Azure Container Apps
    ├── Builds Docker image (tagged with git SHA + latest)
    ├── Pushes to Azure Container Registry
    ├── Updates Container App to new image revision
    ├── Migrations run automatically on container startup
    ├── Smoke test: polls /health/ for up to 2 minutes
    └── Smoke test: verifies /management/ returns 404
```

Push to any branch other than `main` runs CI + Security only — it never deploys.

### Manual deploy (emergency)

If you need to trigger a deploy without a code change:

```bash
# Push an empty commit
git commit --allow-empty -m "chore: trigger deploy"
git push origin main
```

### Roll back to a previous image

```bash
az containerapp update \
  --name <CONTAINER_APP_NAME> \
  --resource-group <RESOURCE_GROUP> \
  --image <ACR_LOGIN_SERVER>/recipesite:<PREVIOUS_GIT_SHA>
```

Find previous SHAs in the GitHub Actions deploy run history or in ACR:

```bash
az acr repository show-tags \
  --name <ACR_NAME> \
  --repository recipesite \
  --orderby time_desc \
  --output table
```

---

## Azure Infrastructure Setup

This section covers one-time setup of the Azure resources needed for deployment. Only required once when setting up from scratch.

### Prerequisites

```bash
az login
az account set --subscription <SUBSCRIPTION_ID>
```

### 1. Create a Resource Group

```bash
az group create \
  --name <RESOURCE_GROUP> \
  --location eastus
```

### 2. Create Azure Container Registry

```bash
az acr create \
  --resource-group <RESOURCE_GROUP> \
  --name <ACR_NAME> \
  --sku Basic

# Enable admin access (used by GitHub Actions to push images)
az acr update --name <ACR_NAME> --admin-enabled true

# Get credentials for GitHub secrets
az acr credential show --name <ACR_NAME>
# → use username as ACR_USERNAME, password as ACR_PASSWORD
# → ACR_LOGIN_SERVER = <ACR_NAME>.azurecr.io
```

### 3. Create Azure Storage Account (for recipe images)

```bash
az storage account create \
  --name <STORAGE_ACCOUNT_NAME> \
  --resource-group <RESOURCE_GROUP> \
  --sku Standard_LRS \
  --kind StorageV2

# Create a container for media uploads
az storage container create \
  --name media \
  --account-name <STORAGE_ACCOUNT_NAME> \
  --public-access blob

# Get the account key for the GitHub secret
az storage account keys list \
  --account-name <STORAGE_ACCOUNT_NAME> \
  --output table
```

### 4. Create Azure Container Apps Environment

```bash
az containerapp env create \
  --name <ENVIRONMENT_NAME> \
  --resource-group <RESOURCE_GROUP> \
  --location eastus
```

### 5. Create Azure Container App

```bash
az containerapp create \
  --name <CONTAINER_APP_NAME> \
  --resource-group <RESOURCE_GROUP> \
  --environment <ENVIRONMENT_NAME> \
  --image <ACR_LOGIN_SERVER>/recipesite:latest \
  --registry-server <ACR_LOGIN_SERVER> \
  --registry-username <ACR_USERNAME> \
  --registry-password <ACR_PASSWORD> \
  --target-port 8000 \
  --ingress external \
  --min-replicas 1 \
  --env-vars \
    DJANGO_SETTINGS_MODULE=config.settings.production \
    DJANGO_SECRET_KEY=<SECRET> \
    DJANGO_ALLOWED_HOSTS=<YOUR_APP_DOMAIN> \
    ADMIN_ENABLED=False \
    DB_NAME=<DB_NAME> \
    DB_USER=<DB_USER> \
    DB_PASSWORD=<DB_PASSWORD> \
    DB_HOST=<DB_HOST> \
    DB_PORT=5432 \
    AZURE_STORAGE_ACCOUNT_NAME=<STORAGE_ACCOUNT_NAME> \
    AZURE_STORAGE_ACCOUNT_KEY=<STORAGE_KEY> \
    AZURE_STORAGE_CONTAINER=media
```

### 6. Set Up OIDC Authentication (replaces AZURE_CREDENTIALS)

OIDC federated credentials let GitHub Actions authenticate to Azure without storing a long-lived secret.

**Create a service principal (if one doesn't exist):**

```bash
az ad sp create-for-rbac \
  --name github-actions-recipe-site \
  --role contributor \
  --scopes /subscriptions/<SUBSCRIPTION_ID>/resourceGroups/<RESOURCE_GROUP>
```

**Get the application (client) ID:**

```bash
az ad app list --display-name github-actions-recipe-site --query "[0].appId" -o tsv
```

**Create the federated credential scoped to the `production` environment:**

```bash
az ad app federated-credential create \
  --id <APP_ID> \
  --parameters '{
    "name": "github-oidc-production",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:casto-tech/recipe_site:environment:production",
    "audiences": ["api://AzureADTokenExchange"]
  }'
```

**Get values for GitHub secrets:**

```bash
# AZURE_CLIENT_ID
az ad app list --display-name github-actions-recipe-site --query "[0].appId" -o tsv

# AZURE_TENANT_ID
az account show --query tenantId -o tsv

# AZURE_SUBSCRIPTION_ID
az account show --query id -o tsv
```

---

## GitHub Actions Secrets

All secrets are set in GitHub → Settings → Secrets and variables → Actions.

| Secret | Where to get it | Used by |
|--------|----------------|---------|
| `AZURE_CLIENT_ID` | `az ad app list --display-name github-actions-recipe-site` | Deploy (OIDC login) |
| `AZURE_TENANT_ID` | `az account show --query tenantId` | Deploy (OIDC login) |
| `AZURE_SUBSCRIPTION_ID` | `az account show --query id` | Deploy (OIDC login) |
| `ACR_LOGIN_SERVER` | `<ACR_NAME>.azurecr.io` | Deploy (image push) |
| `ACR_USERNAME` | `az acr credential show --name <ACR_NAME>` | Deploy (image push) |
| `ACR_PASSWORD` | `az acr credential show --name <ACR_NAME>` | Deploy (image push) |
| `CONTAINER_APP_NAME` | Name of your Container App resource | Deploy (update revision) |
| `RESOURCE_GROUP` | Name of your Azure resource group | Deploy (update revision) |
| `DJANGO_ALLOWED_HOSTS` | Your Container App domain | Deploy (env var injection) |
| `HEALTH_CHECK_URL` | `https://<YOUR_DOMAIN>/health/` | Deploy (smoke test) |

---

## Environment Variables Reference

### Local Development (`.env`)

Copy `.env.example` to `.env`. All values below are for local dev only.

| Variable | Example Value | Description |
|----------|--------------|-------------|
| `DJANGO_SECRET_KEY` | *(generated)* | Django signing key — generate with `secrets.token_urlsafe(64)` |
| `DJANGO_DEBUG` | `True` | Debug mode — always `False` in production |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated allowed hostnames |
| `DJANGO_SETTINGS_MODULE` | `config.settings.development` | Settings module to load |
| `ADMIN_ENABLED` | `True` | Mounts admin at `/management/` — local dev only |
| `DB_NAME` | `recipes` | PostgreSQL database name |
| `DB_USER` | `recipes_user` | PostgreSQL username |
| `DB_PASSWORD` | *(generated)* | PostgreSQL password — generate with `secrets.token_urlsafe(32)` |
| `DB_HOST` | `db` | Docker Compose service name for the database |
| `DB_PORT` | `5432` | PostgreSQL port |
| `AZURE_STORAGE_ACCOUNT_NAME` | *(empty)* | Leave blank — dev uses local `media/` directory |
| `AZURE_STORAGE_ACCOUNT_KEY` | *(empty)* | Leave blank in local dev |
| `AZURE_STORAGE_CONTAINER` | `media` | Blob container name (unused when account name is blank) |

### Production (Azure Container App environment variables)

| Variable | Description |
|----------|-------------|
| `DJANGO_SETTINGS_MODULE` | Must be `config.settings.production` |
| `DJANGO_SECRET_KEY` | Strong random secret — never reuse the dev value |
| `DJANGO_ALLOWED_HOSTS` | Your Container App domain(s), comma-separated |
| `ADMIN_ENABLED` | Must be `False` — enforced by smoke test in deploy pipeline |
| `DB_NAME` | PostgreSQL database name |
| `DB_USER` | PostgreSQL username |
| `DB_PASSWORD` | PostgreSQL password |
| `DB_HOST` | PostgreSQL host (Azure Database for PostgreSQL FQDN) |
| `DB_PORT` | `5432` |
| `AZURE_STORAGE_ACCOUNT_NAME` | Storage account name for media uploads |
| `AZURE_STORAGE_ACCOUNT_KEY` | Storage account key |
| `AZURE_STORAGE_CONTAINER` | Blob container name (default: `media`) |

---

## Security Notes

### Admin is completely absent in production

The Django admin is not just password-protected — it is removed from `INSTALLED_APPS` in the production image:
- No admin database tables are loaded
- No admin views are registered
- No admin URL can ever be mounted
- All `/management/` paths return HTTP 404
- The deploy pipeline verifies this with a smoke test after every deploy

### Production-only security features

- HTTPS enforced (`SECURE_SSL_REDIRECT = True`)
- HSTS for 1 year with subdomains and preload
- Secure, HttpOnly, SameSite=Strict cookies
- Content Security Policy via `django-csp`
- Rate limiting on all endpoints via `django-ratelimit` (reads real client IP through Azure proxy)
- Brute-force lockout after 5 failed logins via `django-axes` (1-hour lockout)
- `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`

### CI/CD security

- All GitHub Actions pinned to full commit SHAs (not tags) to prevent supply chain attacks
- OIDC authentication to Azure — no long-lived credentials stored in GitHub
- Minimum permissions per job — all workflows default to `permissions: {}`
- Container scanned for CVEs on every push (Trivy — fails on fixable HIGH/CRITICAL)
- Python dependencies audited on every push (pip-audit)
- SAST on every push (bandit — fails on HIGH severity findings)
- CodeQL analysis results uploaded to GitHub Security tab

### For full infrastructure security details

See [infrastructure_documentation.md](infrastructure_documentation.md).

---

## Troubleshooting

### Container won't start — "DJANGO_SECRET_KEY environment variable must be set"

You haven't created `.env` yet, or it's missing `DJANGO_SECRET_KEY`.

```bash
cp .env.example .env
# Then edit .env and set DJANGO_SECRET_KEY
```

### Database connection refused on first start

The `db` service needs a moment to initialise. Docker Compose waits for the healthcheck, but if you ran `docker-compose up` without `-d` and interrupted it, the volume may be in a bad state.

```bash
docker-compose down -v
docker-compose up -d
```

### Migrations fail — "relation does not exist"

The database may not have been initialised. Restart the stack:

```bash
docker-compose down -v && docker-compose up -d
```

### Static files return 404 (locally)

Django's dev server serves static files automatically when `DEBUG=True`. If you see 404s for static assets, ensure `DJANGO_DEBUG=True` is set in your `.env`.

### Media images not showing after an upload (locally)

The `media_files` Docker volume persists uploads between restarts. If it's missing, recreate it:

```bash
docker-compose down
docker-compose up -d
```

### Port 8000 already in use

```bash
# Find what's using it
lsof -i :8000

# Or change the port in docker-compose.yml:
ports:
  - "8080:8000"  # access at http://localhost:8080
```

### Deploy pipeline fails at smoke test

The health check polls `/health/` for 2 minutes. If it fails, the previous revision remains active. Check:

1. Azure Container Apps revision logs in the Azure Portal → Container Apps → Revisions → select the new revision → Logs
2. Confirm all required environment variables are set on the Container App
3. Confirm the database is reachable from the Container App

### Check what image is currently running in production

```bash
az containerapp show \
  --name <CONTAINER_APP_NAME> \
  --resource-group <RESOURCE_GROUP> \
  --query "properties.template.containers[0].image" \
  --output tsv
```

### List all images in ACR

```bash
az acr repository show-tags \
  --name <ACR_NAME> \
  --repository recipesite \
  --orderby time_desc \
  --output table
```

### Manually trigger a migration in production

Migrations run automatically on every container restart (via `entrypoint.sh`). To force a restart:

```bash
az containerapp revision restart \
  --name <CONTAINER_APP_NAME> \
  --resource-group <RESOURCE_GROUP> \
  --revision <REVISION_NAME>
```
