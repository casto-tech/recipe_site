# Threat Assessment — Recipe Site
**Date:** 2026-04-18  
**Assessor:** Claude Code (claude-sonnet-4-6)  
**Branch assessed:** `security`  
**Scope:** Django application code, templates, CI/CD pipeline, Dockerfile, GitHub Actions workflows, Azure infrastructure configuration  
**Methodology:** OWASP Top 10, STRIDE

---

## Executive Summary

No Critical or High severity findings. The application has a strong security baseline: ORM-only database access, validated input at all boundaries, HSTS, secure cookies, django-axes brute-force protection, rate limiting with a correct 429 handler, non-root container, admin fully removed from production, OIDC for Azure deployment, and automated CVE scanning on every commit.

Two Medium findings carried over from the previous assessment remain open after a code revert (M-1, M-2). Two new Medium findings were identified in the CI/CD pipeline (M-3, M-4). Two Low findings are new.

**Finding summary:**

| ID     | Severity      | Title                                          | Status    |
|--------|---------------|------------------------------------------------|-----------|
| M-1    | Medium        | Tailwind CDN Play in production — no SRI       | **Fixed** |
| M-2    | Medium        | `style-src 'unsafe-inline'` in CSP             | **Fixed** |
| M-3    | Medium        | Azure Storage Account Key as long-lived secret | Open      |
| M-4    | Medium        | ACR admin credentials in deploy pipeline       | **Fixed** |
| LOW-1  | Low           | Gunicorn `--forwarded-allow-ips '*'`           | Open      |
| LOW-2  | Low           | Missing SRI on Alpine.js (unpkg.com)           | **Fixed** |
| LOW-3  | Low           | Custom 429 handler for rate limit responses    | **Fixed** |
| LOW-4  | Low           | `Permissions-Policy` header absent             | **Fixed** |
| LOW-5  | Low           | `@require_GET` missing on health view          | **Fixed** |
| INFO-1 | Informational | CodeQL findings do not fail CI                 | Accepted  |
| INFO-2 | Informational | Bandit uses `\|\| true` before inline parser   | Accepted  |
| INFO-3 | Informational | `search_vector` field unused in queries        | Note      |
| INFO-4 | Informational | No `Retry-After` header on 429 responses       | Note      |

---

## OWASP Top 10 Assessment

### A01 — Broken Access Control
**Rating: Low Risk**

The application is publicly read-only. No user-facing authentication exists. The Django admin is disabled at the `INSTALLED_APPS` level in production — the app, tables, views, and URL registration are entirely absent. The `management/` path returns HTTP 404. This is verified by a post-deploy smoke test in the CI/CD pipeline. `@require_GET` is enforced on the `search` and `health` views. CSRF is enforced on all state-changing operations.

### A02 — Cryptographic Failures
**Rating: Low Risk**

HTTPS enforced with `SECURE_SSL_REDIRECT = True` and Azure Container Apps TLS termination. HSTS is set to one year with `includeSubdomains` and `preload`. Session and CSRF cookies are `Secure`, `HttpOnly`, and `SameSite=Strict`. `SECRET_KEY` is injected at runtime via environment variable and is never baked into the image. No sensitive data is stored in the application database.

### A03 — Injection
**Rating: Low Risk**

All database access uses the Django ORM exclusively — no raw SQL anywhere in the codebase. `SearchForm` validates and sanitises the `q` and `tag` query parameters before they reach `RecipeManager.search()`. The tag field is restricted by regex to `[a-z0-9\-]+`. Full-text search uses `icontains` (ORM-parameterised). Uploaded image filenames are never rendered back to users.

### A04 — Insecure Design
**Rating: Low Risk**

The application stores only recipe content (no PII, no payment data, no credentials). Attack surface is minimal: three public endpoints (`/`, `/search/`, `/health/`). Rate limiting covers all three. Image uploads are validated by extension, size, and Pillow content inspection. The SSRF validator on `image_url` rejects all private, loopback, link-local, and reserved IP ranges.

### A05 — Security Misconfiguration
**Rating: Medium Risk** (M-1, M-2)

`production.py` currently loads Tailwind CSS from `cdn.tailwindcss.com` without Subresource Integrity (SRI). CDN Play cannot carry a static SRI hash because it generates JavaScript dynamically. As a result, `script-src` includes the CDN domain and `style-src` carries `'unsafe-inline'` (required because CDN Play injects `<style>` tags at runtime). These two directives weaken the Content Security Policy. A fix was implemented and tested on this branch but was subsequently reverted — see M-1 and M-2.

Otherwise, configuration is strong: `DEBUG = False`, no stack traces, `ALLOWED_HOSTS` enforced, `X_FRAME_OPTIONS = DENY`, `SECURE_CONTENT_TYPE_NOSNIFF`, `SECURE_REFERRER_POLICY`, `Permissions-Policy` applied via `django-permissions-policy`.

### A06 — Vulnerable and Outdated Components
**Rating: Low Risk**

`pip-audit` runs on every CI push and blocks the pipeline on any HIGH or CRITICAL CVE in installed packages. Trivy scans the Docker image for OS-level CVEs and blocks on fixable HIGH/CRITICAL findings. Dependabot opens weekly PRs for Python dependencies and GitHub Actions. All Actions are pinned to full commit SHAs — no floating version tags. `apt-get upgrade -y` runs in both Dockerfile stages to patch available OS CVEs at build time.

### A07 — Identification and Authentication Failures
**Rating: Low Risk**

No public login surface exists. Admin login (dev only) is protected by `django-axes`: five failures triggers a one-hour IP lockout. `AXES_LOCKOUT_PARAMETERS = ["ip_address"]` and `AXES_RESET_ON_SUCCESS = True`. Auth password validators enforce minimum length, common password rejection, and similarity checks.

### A08 — Software and Data Integrity Failures
**Rating: Medium Risk** (M-1, M-4)

Tailwind CDN Play removed from production (M-1 fixed). Alpine.js is now self-hosted in `static/js/` (LOW-2 fixed). HTMX loads from `unpkg.com` with a pinned SRI hash. The deploy pipeline uses OIDC federated credentials for both Azure login and ACR (M-4 fixed). Actions are pinned to commit SHAs, preventing action supply-chain substitution.

### A09 — Security Logging and Monitoring Failures
**Rating: Low Risk**

Structured JSON logging is written to stdout and captured by Azure Monitor in production. `django.request` and `django.security` loggers are at WARNING level. `axes` logs lockout events. Rate-limit hits now return HTTP 429 (correct), but the `ratelimited` view does not emit a log entry — a spike in 429s is only visible via Azure Monitor request-count metrics, not via the application log stream.

### A10 — Server-Side Request Forgery (SSRF)
**Rating: Low Risk**

`validate_no_private_url` in `recipes/validators.py` blocks all private RFC-1918 ranges, loopback, link-local, multicast, and unspecified addresses on the `image_url` field. The validator rejects `localhost`, `localhost.localdomain`, and any IP address in a reserved range. HTTP and HTTPS are the only permitted schemes. The validator is applied at the model level.

---

## STRIDE Analysis

| Threat              | Controls in place                                                                                    | Gap                                                            |
|---------------------|------------------------------------------------------------------------------------------------------|----------------------------------------------------------------|
| **Spoofing**        | OIDC federated credentials for Azure deploy; django-axes IP lockout; CSRF tokens                     | ACR uses admin creds (M-4); X-Forwarded-For spoofable (LOW-1) |
| **Tampering**       | CSRF enforced; image upload validated by extension + size + Pillow verify; ORM parameterised queries | None significant                                               |
| **Repudiation**     | Structured JSON logging to Azure Monitor; axes lockout events logged                                 | Rate-limit events not explicitly logged                        |
| **Info Disclosure** | DEBUG=False; no stack traces; generic error pages; no sensitive data in DB                           | None significant                                               |
| **DoS**             | Rate limiting (60/m index, 30/m search, 60/m health); correct 429 response; health endpoint is DB-free | `--forwarded-allow-ips '*'` allows rate-limit bypass via IP spoofing (LOW-1) |
| **EoP**             | Non-root container user (`appuser`); admin removed from INSTALLED_APPS in prod; no privilege paths   | None significant                                               |

---

## Open Findings

---

### M-1 — Tailwind CDN Play loaded in production without SRI ✓ Fixed
**Severity:** Medium

Tailwind CDN Play removed from production. The standalone Tailwind CLI is downloaded in the Docker builder stage, used to compile `tailwind.output.css` in the final stage, then deleted — it never ships at runtime. `base.html` uses `{% if debug %}` to load CDN Play only in local dev; production receives `<link rel="stylesheet" href="{% static 'css/tailwind.output.css' %}">` served via WhiteNoise. `cdn.tailwindcss.com` removed from `CSP_SCRIPT_SRC`.

### M-2 — `'unsafe-inline'` in `style-src` CSP ✓ Fixed
**Severity:** Medium

`'unsafe-inline'` and `cdn.tailwindcss.com` removed from `CSP_STYLE_SRC`. All `style=""` inline attributes and `<style>` blocks in templates moved to `app.css` as named classes (`.hero-section`, `.footer-section`, `.hero-title`, `.search-bar-spacer`, `.frosted-bar-pinned`, `.frosted-dropdown`). `style="display:none"` on Alpine.js `x-show` elements replaced with `x-cloak`; `[x-cloak] { display: none !important; }` added to `app.css`.

---

### M-3 — Azure Storage Account Key stored as a long-lived GitHub secret
**Severity:** Medium  
**Location:** `config/settings/base.py` → `AZURE_ACCOUNT_KEY`; GitHub Actions secrets (`AZURE_STORAGE_ACCOUNT_KEY`)

**Description:**  
`AZURE_ACCOUNT_KEY` is a full-access key to the Azure Storage account. It grants unrestricted read, write, and delete on all containers in the account — including media files. Long-lived account keys do not expire, cannot be scoped to a single container, and cannot be revoked without rotating the key (which requires updating the secret everywhere it is stored).

**Fix:**  
Assign a managed identity to the Azure Container App and grant it `Storage Blob Data Contributor` on the media container only. Remove `AZURE_ACCOUNT_KEY` from settings and GitHub secrets. `django-storages` supports `DefaultAzureCredential` when no key is configured. The existing OIDC service principal can be granted the same RBAC role for CI use.

**Effort:** Medium — requires Azure RBAC assignment and a settings change; no application logic changes.

---

### LOW-1 — Gunicorn `--forwarded-allow-ips '*'` enables X-Forwarded-For spoofing
**Severity:** Low  
**Location:** `entrypoint.sh` → `gunicorn ... --forwarded-allow-ips '*'`

**Description:**  
`--forwarded-allow-ips '*'` instructs Gunicorn to trust the `X-Forwarded-For` header from any upstream IP. Django's `REMOTE_ADDR` is then set to the first value in that header. `django-ratelimit` and `django-axes` both key on `REMOTE_ADDR`. A client that can set its own `X-Forwarded-For` header can cycle through arbitrary IPs and bypass rate limiting and brute-force lockouts.

In Azure Container Apps the ingress IP range is not publicly documented and can change, making specific allowlisting impractical. The `*` setting is a common workaround for ACA deployments, but the risk to IP-based controls is real.

**Fix:**  
If Azure Container Apps exposes a stable internal CIDR for ingress, restrict to that range: `--forwarded-allow-ips '<CIDR>'`. Otherwise, document the accepted risk and consider supplementing IP-based controls with connection-level signals. No code change recommended until the Azure ingress IP range is confirmed.

**Effort:** Low to investigate; mitigation depends on Azure network configuration.

---

### LOW-2 — Missing SRI on Alpine.js loaded from unpkg.com ✓ Fixed
**Severity:** Low

Alpine.js 3.14.1 downloaded to `static/js/alpinejs.min.js` and served via WhiteNoise. The `unpkg.com` CDN reference removed from `base.html`. `https://unpkg.com` remains in `CSP_SCRIPT_SRC` for HTMX (which retains its SRI hash).

---

## Fixed Findings

### M-4 — ACR admin credentials replaced with OIDC + `az acr login` ✓ Fixed
`docker/login-action` (admin creds) removed from `build-and-push` job. `azure/login` (OIDC) added to that job with `id-token: write` permission. `az acr login --name` authenticates Docker to ACR using the short-lived OIDC token. `ACR_USERNAME` and `ACR_PASSWORD` secrets can now be deleted from GitHub. Prerequisite: grant the OIDC service principal `AcrPush` role on the registry via `az role assignment create`.

### LOW-3 — Custom 429 handler for django-ratelimit ✓ Fixed
`RATELIMIT_VIEW = "recipes.views.ratelimited"` added to `base.py`. The `ratelimited` view in `recipes/views.py` returns HTTP 429 with `content_type="text/plain"`. Rate-limited requests no longer return the misleading HTTP 403.

### LOW-4 — `Permissions-Policy` header absent ✓ Fixed
`django-permissions-policy` added to `requirements.txt` and `MIDDLEWARE`. `PERMISSIONS_POLICY` block in `base.py` disables accelerometer, camera, geolocation, gyroscope, magnetometer, microphone, payment, and USB for all origins.

### LOW-5 — `@require_GET` missing on health view ✓ Fixed
`@require_GET` decorator added to `recipes/views.py`. Non-GET requests to `/health/` now return HTTP 405 Method Not Allowed.

---

## Informational Notes

### INFO-1 — CodeQL findings do not fail CI
CodeQL analysis uploads SARIF results to the GitHub Security tab but does not set `exit-code: 1`. This is an accepted design choice — persistent tracking without blocking every push. Security tab findings should be reviewed on a regular cadence.

### INFO-2 — Bandit uses `|| true` before inline Python parser
`bandit ... -o bandit-report.json || true` suppresses bandit's own exit code. The inline Python script reads the JSON and exits 1 on HIGH findings. If bandit crashes with a non-JSON error the Python script will also fail, so the gate still holds. The pattern is fragile but does not create a bypass.

### INFO-3 — `search_vector` field populated but unused in queries
`Recipe.search_vector` is a `SearchVectorField` with a GIN index. `RecipeManager.search()` uses `icontains` rather than `SearchQuery` / `SearchRank`. The field and index exist but provide no query benefit. If full-text search ranking is desired, migrate the search method to use `SearchQuery`. Otherwise, the field is safe dead weight.

### INFO-4 — No `Retry-After` header on 429 responses
The `ratelimited` view returns HTTP 429 but omits the `Retry-After` header recommended by RFC 6585. Without it, HTTP clients may retry immediately or back off arbitrarily. Low priority for a public read-only site with no automated API clients.

---

## Recommended Fix Order

1. ~~**M-4**~~ ✓ Done — ACR admin credentials replaced with OIDC + `az acr login`.
2. ~~**M-1 + M-2**~~ ✓ Done — Tailwind compiled to static bundle; CDN Play removed from production; `'unsafe-inline'` stripped from CSP.
3. ~~**LOW-2**~~ ✓ Done — Alpine.js self-hosted in `static/js/`; CDN dependency removed.
4. **M-3** — Migrate Azure Storage to managed identity. Requires Azure RBAC changes; no application code changes.
5. **LOW-1** — Investigate Azure Container Apps ingress CIDR; restrict `--forwarded-allow-ips` if a stable range can be confirmed.
