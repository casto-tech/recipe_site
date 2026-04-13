# Infrastructure Documentation — Recipe Site

## Overview

The recipe site is a Django 5 application hosted on **Azure Container Apps**, using a fully automated CI/CD pipeline via **GitHub Actions**. Images are stored in **Azure Container Registry (ACR)**, media uploads go to **Azure Blob Storage**, and the database is **PostgreSQL**. All infrastructure components are hardened to follow the principle of least privilege.

---

## Architecture

```
Internet
    │
    ▼
Azure Container Apps (HTTPS, TLS termination)
    │  X-Forwarded-Proto: https
    │  X-Forwarded-For: <client IP>
    ▼
Gunicorn (--forwarded-allow-ips '*')
    │
    ▼
Django 5 Application (Python 3.12)
    │
    ├──► PostgreSQL (Azure Database for PostgreSQL)
    ├──► Azure Blob Storage (media uploads)
    └──► Azure Container Registry (source of deployed image)

Static assets served by WhiteNoise (bundled in container, no CDN needed)
```

### Key Components

| Component | Service | Notes |
|-----------|---------|-------|
| Application runtime | Azure Container Apps | Serverless container hosting, auto-scales |
| Container registry | Azure Container Registry (ACR) | Stores built Docker images |
| Database | Azure Database for PostgreSQL | Managed, not exposed publicly |
| Media storage | Azure Blob Storage | Recipe images uploaded by admins |
| Static files | WhiteNoise (in-container) | Compressed + content-hashed at build time |
| Logs | Azure Monitor | Structured JSON log output from Gunicorn |

---

## Docker Image

### Multi-stage Build

The `Dockerfile` uses a two-stage build to keep the final image small and free of build tools:

**Stage 1 — Builder:**
- Base: `python:3.12-slim`
- Installs `libpq-dev`, `gcc` (needed to compile `psycopg2`)
- Runs `apt-get upgrade` to apply OS security patches before Trivy scans
- Installs Python packages into `/install` prefix

**Stage 2 — Final Image:**
- Base: `python:3.12-slim` (clean, no compiler)
- Copies `/install` from builder — no build tools ship in the final image
- Creates non-root system user `appuser:appgroup`
- Runs `collectstatic` at build time (using a placeholder `SECRET_KEY`)
- Switches to `appuser` before `EXPOSE` and `CMD`
- The real `SECRET_KEY` is **never baked into the image** — injected at runtime via Container Apps environment variables

### Container Startup (`entrypoint.sh`)

On every container start:
1. `python manage.py migrate --noinput` — runs pending database migrations automatically
2. `gunicorn` starts with a dynamically calculated worker count: `(2 × CPU cores) + 1`

```sh
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers $((2 * $(nproc --all 2>/dev/null || echo 1) + 1)) \
    --timeout 60 \
    --forwarded-allow-ips '*'
```

`--forwarded-allow-ips '*'` is required so Gunicorn trusts the `X-Forwarded-For` header from the Azure Container Apps load balancer. Without this, `REMOTE_ADDR` (used by rate limiting) would always be the proxy IP, not the real client IP.

---

## CI/CD Pipeline

The pipeline is defined across four workflow files under `.github/workflows/`:

```
pipeline.yml         ← Orchestrator; calls the three reusable workflows
├── ci.yml           ← Tests, linting, coverage
├── security.yml     ← SAST, CVE scanning, CodeQL, container scan
└── deploy.yml       ← Build, push to ACR, deploy to Container Apps
```

### Pipeline Flow

```
git push (any branch)
        │
        ▼
    CI — Tests & Linting
        │ (must pass)
        ▼
    Security — SAST, CVE & Image Scan
        │ (must pass)
        ▼
    Deploy (only if: branch == main AND event == push)
```

Pull requests to `main` run CI + Security but never deploy.

### CI (`ci.yml`)

- Spins up a real PostgreSQL 16 service container (no mocked DB)
- Runs `flake8` (linting), `black --check` (formatting), `pytest` with `--cov-fail-under=80`
- Coverage report uploaded as artifact (7-day retention)
- `ADMIN_ENABLED=True` in CI so security tests can verify admin is available in dev

### Security (`security.yml`)

| Job | Tool | Gate |
|-----|------|------|
| Python CVE Audit | `pip-audit` | Fails on any CVE found in installed packages |
| Python SAST | `bandit` | Fails on any HIGH severity finding |
| CodeQL Analysis | GitHub CodeQL | Reports to Security tab, does not fail pipeline |
| Docker Image Scan | Trivy v0.20.0 | Fails on any fixable HIGH/CRITICAL CVE in container |

Trivy runs twice:
1. **Table format** — the security gate; fails the job if fixable HIGH/CRITICAL CVEs exist
2. **SARIF format** — reporting only; uploads to GitHub Security tab regardless of gate result

### Deploy (`deploy.yml`)

**Job 1 — Build & Push:**
- Builds the Docker image using GitHub Actions cache (`type=gha`)
- Tags image with both `:<git-sha>` (immutable, used for deployment) and `:latest` (mutable, for reference)
- Pushes to ACR; verifies push via `docker manifest inspect`

**Job 2 — Deploy:**
- Logs into Azure via OIDC (see [Authentication](#oidc-authentication-to-azure))
- Runs `az containerapp update` with the new SHA-tagged image
- Database migrations run automatically on container startup
- Runs two smoke tests after deploy:
  1. Polls `/health/` for up to 2 minutes; fails if it never returns HTTP 200
  2. Verifies `/management/` (admin) returns HTTP 404 (confirms admin is absent in production)

### Concurrency Controls

| Scope | Behaviour |
|-------|-----------|
| `pipeline-${{ github.ref }}` | Cancels in-progress pipeline runs on the same branch/PR |
| `deploy-production` | Cancels an in-progress deploy before starting a new one (prevents race conditions on the Container App) |

---

## OIDC Authentication to Azure

The deploy workflow uses **OIDC federated credentials** — no long-lived `AZURE_CREDENTIALS` JSON secret is stored in GitHub.

**How it works:**
1. GitHub Actions generates a short-lived OIDC token per run, signed by `https://token.actions.githubusercontent.com`
2. Azure verifies the token against GitHub's JWKS endpoint
3. Azure issues a short-lived access token scoped to the subscription
4. Token is valid only for the duration of the workflow run

**Federated credential constraint:**
- Issuer: `https://token.actions.githubusercontent.com`
- Subject: `repo:casto-tech/recipe_site:environment:production`
- Only deploys from the `production` GitHub environment can authenticate

**Required GitHub secrets:**

| Secret | Description |
|--------|-------------|
| `AZURE_CLIENT_ID` | Application (client) ID of the service principal |
| `AZURE_TENANT_ID` | Azure Active Directory tenant ID |
| `AZURE_SUBSCRIPTION_ID` | Azure subscription ID |

**Required permission:**
- The deploy job has `id-token: write` to allow requesting OIDC tokens from GitHub

---

## GitHub Actions Security

### Permissions Model

All workflows use `permissions: {}` at the top level (deny all by default). Each job grants only the minimum permissions it requires:

| Job | Permissions |
|-----|-------------|
| CI | `contents: read` |
| Security / dependency-audit | `contents: read` |
| Security / sast | `contents: read` |
| Security / codeql | `contents: read`, `actions: read`, `security-events: write` |
| Security / trivy | `contents: read`, `security-events: write` |
| Deploy / build-and-push | `contents: read` |
| Deploy / deploy | `contents: read`, `id-token: write` |

### SHA-Pinned Actions

Every third-party action is pinned to a full commit SHA (not a tag), with the version in a comment. This prevents supply chain attacks where a tag is force-pushed to a malicious commit.

```yaml
uses: actions/checkout@93cb6efe18208431cddfb8368fd83d5badbf9bfd  # v5
uses: docker/login-action@4907a6ddec9925e35a0a9e82d7399ccc52663121  # v4.1.0
uses: azure/login@532459ea530d8321f2fb9bb10d1e0bcf23869a43       # v3.0.0
```

### Secret Handling

- Secrets are never echoed into job outputs (removed `image-tag` output that contained `ACR_LOGIN_SERVER`)
- Build-time `DJANGO_SECRET_KEY` uses a placeholder value; the real secret is injected at runtime only
- `AZURE_CREDENTIALS` (long-lived JSON secret) has been replaced by OIDC (three non-sensitive IDs)

---

## Django Application Security

### Production Settings (`config/settings/production.py`)

| Setting | Value | Purpose |
|---------|-------|---------|
| `DEBUG` | `False` | Never expose stack traces |
| `ADMIN_ENABLED` | `False` | Admin removed from `INSTALLED_APPS` entirely |
| `SECURE_SSL_REDIRECT` | `True` | Force all traffic to HTTPS |
| `SECURE_PROXY_SSL_HEADER` | `HTTP_X_FORWARDED_PROTO: https` | Trust Azure's SSL termination |
| `SESSION_COOKIE_SECURE` | `True` | Cookie only sent over HTTPS |
| `SESSION_COOKIE_HTTPONLY` | `True` | Cookie not accessible via JavaScript |
| `SESSION_COOKIE_SAMESITE` | `Strict` | Prevent CSRF via cross-site requests |
| `SESSION_COOKIE_AGE` | `3600` (1 hour) | Session expires after inactivity |
| `CSRF_COOKIE_SECURE` | `True` | CSRF token only sent over HTTPS |
| `CSRF_COOKIE_SAMESITE` | `Strict` | CSRF token not sent cross-site |
| `SECURE_HSTS_SECONDS` | `31536000` (1 year) | Force HTTPS for 1 year via HSTS header |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` | `True` | HSTS applies to all subdomains |
| `SECURE_HSTS_PRELOAD` | `True` | Eligible for browser HSTS preload list |

### Django Admin — Completely Removed in Production

The admin interface is not just disabled — it is removed from `INSTALLED_APPS`:

```python
INSTALLED_APPS = [app for app in INSTALLED_APPS if app != "django.contrib.admin"]
```

This means:
- No admin database tables are loaded
- No admin views are registered
- No admin URL can be mounted
- All `/management/` paths return HTTP 404
- The smoke test in the deploy pipeline verifies this after every deploy

### Content Security Policy

Configured via `django-csp` middleware, appended only in production:

| Directive | Allowed Sources | Notes |
|-----------|----------------|-------|
| `default-src` | `'self'` | Baseline for all resource types |
| `script-src` | `'self'`, Tailwind CDN, unpkg | No `unsafe-inline` for scripts |
| `style-src` | `'self'`, `'unsafe-inline'`, Tailwind CDN, Google Fonts | `unsafe-inline` required by Tailwind CDN Play (injects `<style>` tags) — known technical debt |
| `img-src` | `'self'`, `data:`, Azure Blob Storage domain | Blob domain added dynamically from env var |
| `font-src` | `'self'`, Google Fonts CDN | |
| `connect-src` | `'self'` | No external API calls from the browser |
| `frame-ancestors` | `'none'` | Prevents clickjacking (equivalent to `X-Frame-Options: DENY`) |
| `base-uri` | `'none'` | Prevents `<base>` tag injection |
| `form-action` | `'self'` | Forms can only submit to this origin |

### Rate Limiting (`django-ratelimit`)

| Endpoint | Rate | Key |
|----------|------|-----|
| `GET /` (index) | 60 req/min | Client IP |
| `GET /search/` | 30 req/min | Client IP |
| `GET /health/` | 60 req/min | Client IP |

Rate limiting reads `REMOTE_ADDR`, which Gunicorn rewrites from `X-Forwarded-For` due to `--forwarded-allow-ips '*'`. Without this, all requests would appear to come from the Azure proxy IP and rate limiting would be ineffective.

### Brute-Force Protection (`django-axes`)

| Setting | Value |
|---------|-------|
| `AXES_FAILURE_LIMIT` | 5 failed login attempts |
| `AXES_COOLOFF_TIME` | 1 hour lockout |
| `AXES_LOCKOUT_PARAMETERS` | IP address |
| `AXES_RESET_ON_SUCCESS` | Counter resets after successful login |
| `AXES_VERBOSE` | `False` — never logs sensitive request data |

### Additional Security Headers

| Header | Value | Set By |
|--------|-------|--------|
| `X-Frame-Options` | `DENY` | `django.middleware.clickjacking.XFrameOptionsMiddleware` |
| `X-Content-Type-Options` | `nosniff` | `SECURE_CONTENT_TYPE_NOSNIFF = True` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | `SECURE_REFERRER_POLICY` |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains; preload` | `SECURE_HSTS_*` settings |
| `Content-Security-Policy` | (see above) | `django-csp` middleware |

### Media Storage

In production, uploaded images are stored in **Azure Blob Storage** via `django-storages[azure]`. The container is named `media` by default (configurable via `AZURE_STORAGE_CONTAINER`). Served directly from `<account>.blob.core.windows.net/<container>/`.

In development, media files are stored locally on disk.

### Logging

Structured JSON output to stdout — captured and indexed by Azure Monitor:

```json
{"time": "...", "level": "INFO", "logger": "recipes", "message": "..."}
```

- No log files are written inside the container (ephemeral filesystem)
- `django.security` and `axes` loggers report at WARNING level
- Sensitive request data is never logged (`AXES_VERBOSE = False`)

---

## Environment Variables

### Required in Production (Container Apps)

| Variable | Description |
|----------|-------------|
| `DJANGO_SECRET_KEY` | Cryptographic secret; must be unique and random |
| `DJANGO_SETTINGS_MODULE` | Must be `config.settings.production` |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated list of allowed hostnames |
| `DB_NAME` | PostgreSQL database name |
| `DB_USER` | PostgreSQL username |
| `DB_PASSWORD` | PostgreSQL password |
| `DB_HOST` | PostgreSQL host |
| `DB_PORT` | PostgreSQL port (default: 5432) |
| `AZURE_STORAGE_ACCOUNT_NAME` | Storage account name for media uploads |
| `AZURE_STORAGE_ACCOUNT_KEY` | Storage account key |
| `AZURE_STORAGE_CONTAINER` | Blob container name (default: `media`) |

### Required in GitHub Secrets (for CI/CD)

| Secret | Used By |
|--------|---------|
| `AZURE_CLIENT_ID` | OIDC login to Azure (deploy) |
| `AZURE_TENANT_ID` | OIDC login to Azure (deploy) |
| `AZURE_SUBSCRIPTION_ID` | OIDC login to Azure (deploy) |
| `ACR_LOGIN_SERVER` | ACR hostname (e.g. `myacr.azurecr.io`) |
| `ACR_USERNAME` | ACR service principal username |
| `ACR_PASSWORD` | ACR service principal password |
| `CONTAINER_APP_NAME` | Azure Container App name |
| `RESOURCE_GROUP` | Azure resource group name |
| `DJANGO_ALLOWED_HOSTS` | Injected into Container App on each deploy |
| `HEALTH_CHECK_URL` | Full URL to `/health/` for smoke tests |

---

