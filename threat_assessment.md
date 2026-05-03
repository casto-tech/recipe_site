# Threat Assessment — Recipe Site
**Date:** 2026-05-03  
**Assessor:** Claude Code (claude-sonnet-4-6)  
**Branch assessed:** `security`  
**Scope:** Django application code, templates, CI/CD pipeline, Dockerfile, GitHub Actions workflows, Azure infrastructure configuration  
**Methodology:** OWASP Top 10, STRIDE

---

## Executive Summary

No Critical or High severity findings. The application has materially improved since the previous assessment: Tailwind is compiled to a static bundle (no CDN Play in production), Alpine.js is self-hosted, the Content Security Policy has no `'unsafe-inline'` directives, ACR authentication uses OIDC instead of long-lived admin credentials, and every rate-limited request returns a correct HTTP 429. The remaining open items are one Medium finding (Azure Storage Account Key), one Low finding carried from the previous cycle (Gunicorn forwarded-allow-ips), and two new Low findings. 

**Finding summary:**

| ID     | Severity      | Title                                           | Status    |
|--------|---------------|-------------------------------------------------|-----------|
| M-1    | Medium        | Tailwind CDN Play in production — no SRI        | **Fixed** |
| M-2    | Medium        | `style-src 'unsafe-inline'` in CSP              | **Fixed** |
| M-3    | Medium        | Azure Storage Account Key as long-lived secret  | Open      |
| M-4    | Medium        | ACR admin credentials in deploy pipeline        | **Fixed** |
| LOW-1  | Low           | Gunicorn `--forwarded-allow-ips '*'`            | Open      |
| LOW-2  | Low           | Missing SRI on Alpine.js (unpkg.com)            | **Fixed** |
| LOW-3  | Low           | Custom 429 handler for rate limit responses     | **Fixed** |
| LOW-4  | Low           | `Permissions-Policy` header absent              | **Fixed** |
| LOW-5  | Low           | `@require_GET` missing on health view           | **Fixed** |
| LOW-6  | Low           | `@require_GET` missing on index view            | **Fixed** |
| LOW-7  | Low           | HTMX loaded from external CDN (unpkg.com)       | **Fixed** |
| INFO-1 | Informational | CodeQL findings do not fail CI                  | Accepted  |
| INFO-2 | Informational | Bandit uses `\|\| true` before inline parser    | Accepted  |
| INFO-3 | Informational | `search_vector` field unused in queries         | Note      |
| INFO-4 | Informational | No `Retry-After` header on 429 responses        | **Fixed** |
| INFO-5 | Informational | Google Fonts loaded from external CDN           | Note      |
| INFO-6 | Informational | `secrets: inherit` passes all secrets to CI jobs | **Fixed** |

---

## OWASP Top 10 Assessment

### A01 — Broken Access Control
**Rating: Low Risk**

The application is publicly read-only with no user-facing authentication. The Django admin is disabled at the `INSTALLED_APPS` level in production — the app, tables, views, and URL registration are entirely absent. The `/management/` path returns HTTP 404; the deploy pipeline smoke-tests this after every deployment. `@require_GET` is enforced on `search` and `health`; the `index` view is missing this decorator (see LOW-6). CSRF is enforced on all state-changing operations. `form-action: 'self'` in the CSP prevents cross-origin form submission.

### A02 — Cryptographic Failures
**Rating: Low Risk**

HTTPS is enforced via `SECURE_SSL_REDIRECT = True` and Azure Container Apps TLS termination. HSTS is set to one year with `includeSubDomains` and `preload`. Session and CSRF cookies are `Secure`, `HttpOnly`, and `SameSite=Strict`. `SECRET_KEY` is injected at runtime via environment variable and is never baked into the image; a build-time placeholder is used only for `collectstatic`. No sensitive data is stored in the application database.

### A03 — Injection
**Rating: Low Risk**

All database access uses the Django ORM exclusively — no raw SQL exists in the codebase. `SearchForm` validates and sanitises `q` and `tag` query parameters before they reach `RecipeManager.search()`. The `tag` field is restricted by regex to `[a-z0-9\-]+`. Full-text search uses `icontains` (ORM-parameterised). Uploaded image filenames are never rendered back to users. The `format_html` helper in `admin.py` escapes the `image_url` before rendering a thumbnail — no XSS surface there.

### A04 — Insecure Design
**Rating: Low Risk**

The application stores only recipe content — no PII, no payment data, no credentials. The attack surface is minimal: three public endpoints (`/`, `/search/`, `/health/`). Rate limiting covers all three. Image uploads are validated by extension, file size (5 MB cap), and Pillow content inspection — extension/content mismatch is detected and rejected. The SSRF validator on `image_url` rejects all private, loopback, link-local, and reserved IP ranges using Python's `ipaddress` module; `localhost` and `localhost.localdomain` are rejected by name before IP parsing.

### A05 — Security Misconfiguration
**Rating: Low Risk**

`DEBUG = False` in production. No stack traces are exposed in error responses (verified by the test suite). `ALLOWED_HOSTS` is enforced. Tailwind CDN Play has been removed from production — the standalone CLI compiles `tailwind.output.css` at Docker build time. Alpine.js is self-hosted in `static/js/`. HTMX is loaded from `unpkg.com` with a pinned SRI hash; the CSP `script-src` still includes `https://unpkg.com` to support this (see LOW-7). No `'unsafe-inline'` directives in `script-src` or `style-src`. `Permissions-Policy` disables eight browser APIs (`camera`, `geolocation`, `microphone`, `payment`, etc.) via `django-permissions-policy`. `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, and `Referrer-Policy: strict-origin-when-cross-origin` are set globally.

### A06 — Vulnerable and Outdated Components
**Rating: Low Risk**

`pip-audit` runs on every CI push and blocks the pipeline on any unfixed CVE in installed packages. One CVE (`CVE-2026-3219` in pip itself) is suppressed with `--ignore-vuln` because no fix version exists; a comment in the workflow flags this for removal when pip ships a patch. Trivy scans the Docker image for OS-level CVEs and blocks on fixable HIGH/CRITICAL findings. Dependabot opens weekly PRs for Python dependencies and GitHub Actions. All Actions are pinned to full commit SHAs — no floating version tags. `apt-get upgrade -y` runs in both Dockerfile stages to apply available OS security patches at build time.

### A07 — Identification and Authentication Failures
**Rating: Low Risk**

No public login surface exists. Admin login (development only) is protected by `django-axes`: five failures triggers a one-hour IP lockout. `AXES_LOCKOUT_PARAMETERS = ["ip_address"]` and `AXES_RESET_ON_SUCCESS = True`. `AXES_VERBOSE = False` ensures no sensitive request data is ever logged. Auth password validators enforce minimum length, common password rejection, and similarity checks.

### A08 — Software and Data Integrity Failures
**Rating: Low Risk**

Alpine.js (3.14.1) is self-hosted — no external CDN dependency. HTMX (1.9.10) is loaded from `unpkg.com` with a pinned SHA-384 SRI hash; the browser will reject any file that does not match the declared hash (see LOW-7 for self-hosting option). Tailwind CSS is compiled from source at build time by the standalone CLI binary, which is then deleted — no Tailwind CDN in production. All GitHub Actions are pinned to full commit SHAs. OIDC federated credentials are used for both the Azure login and ACR authentication — no long-lived `AZURE_CREDENTIALS` JSON or ACR admin password is stored in GitHub secrets.

### A09 — Security Logging and Monitoring Failures
**Rating: Low Risk**

Structured JSON logging is written to stdout and captured by Azure Monitor in production. `django.request` and `django.security` loggers are at WARNING level. `axes` logs lockout events. The `ratelimited` view returns HTTP 429 but does not emit an explicit log entry — rate-limit spikes are visible via Azure Monitor request-count metrics but not via the application log stream (see INFO-4).

### A10 — Server-Side Request Forgery (SSRF)
**Rating: Low Risk**

`validate_no_private_url` in `recipes/validators.py` blocks all private RFC-1918 ranges, loopback, link-local, multicast, and unspecified addresses on the `image_url` field. `localhost` and `localhost.localdomain` are rejected explicitly before IP parsing. Only HTTP and HTTPS schemes are permitted. The validator is applied at the model level and is the only pathway through which a URL is ever stored. Image URLs are not fetched server-side at request time — they are stored and rendered as `<img src>` attributes, so SSRF risk is limited to the storage path.

---

## STRIDE Analysis

| Threat              | Controls in place                                                                                         | Gap                                                                           |
|---------------------|-----------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------|
| **Spoofing**        | OIDC federated credentials for Azure deploy; django-axes IP lockout; CSRF tokens; `SameSite=Strict` cookies | X-Forwarded-For spoofable (LOW-1)                                          |
| **Tampering**       | CSRF enforced; image upload validated by extension + size + Pillow verify; ORM parameterised queries; SRI on HTMX | None significant                                                        |
| **Repudiation**     | Structured JSON logging to Azure Monitor; axes lockout events logged                                      | Rate-limit events not explicitly logged (INFO-4)                              |
| **Info Disclosure** | `DEBUG=False`; no stack traces; generic error pages; no sensitive data in DB; `AXES_VERBOSE=False`        | None significant                                                              |
| **DoS**             | Rate limiting (60/m index, 30/m search, 60/m health); correct 429 response; DB-free health endpoint       | `--forwarded-allow-ips '*'` allows rate-limit bypass via IP spoofing (LOW-1) |
| **EoP**             | Non-root container user (`appuser`); admin removed from `INSTALLED_APPS` in production; no privilege paths | Azure Storage key grants unrestricted blob access (M-3)                      |

---

## Open Findings

---

### M-3 — Azure Storage Account Key stored as a long-lived GitHub secret
**Severity:** Medium  
**Location:** `config/settings/base.py` → `AZURE_ACCOUNT_KEY`; GitHub Actions secrets (`AZURE_STORAGE_ACCOUNT_KEY`)

**Description:**  
`AZURE_ACCOUNT_KEY` is a full-access key to the Azure Storage account. It grants unrestricted read, write, and delete on all containers in the account — including the `media` container. Long-lived account keys do not expire, cannot be scoped to a single container, and require key rotation to revoke — which requires updating the secret in every location where it is stored.

**Fix:**  
Assign a managed identity to the Azure Container App and grant it `Storage Blob Data Contributor` on the media container only. Remove `AZURE_ACCOUNT_KEY` from `base.py` and from GitHub secrets. `django-storages` supports `DefaultAzureCredential` (which picks up the managed identity automatically) when no key is configured:

```python
# base.py — remove AZURE_ACCOUNT_KEY entirely
if AZURE_ACCOUNT_NAME:
    DEFAULT_FILE_STORAGE = "storages.backends.azure_storage.AzureStorage"
    # No AZURE_ACCOUNT_KEY — DefaultAzureCredential picks up the managed identity
```

Grant the existing OIDC service principal `Storage Blob Data Contributor` on the container for CI use.

**Effort:** Medium — requires Azure RBAC assignment and a settings change; no application logic changes.

---

### LOW-1 — Gunicorn `--forwarded-allow-ips '*'` enables X-Forwarded-For spoofing
**Severity:** Low  
**Location:** `entrypoint.sh`

**Description:**  
`--forwarded-allow-ips '*'` instructs Gunicorn to trust the `X-Forwarded-For` header from any upstream IP. Django's `REMOTE_ADDR` is then set to the first value in that header. `django-ratelimit` and `django-axes` both key on `REMOTE_ADDR`. A client that can set its own `X-Forwarded-For` header can cycle through arbitrary IPs and bypass rate limiting and brute-force lockouts.

In Azure Container Apps the ingress IP range is not publicly documented and can change, making specific allowlisting impractical without network configuration work. The `*` setting is a common workaround for ACA deployments.

**Fix:**  
If Azure Container Apps exposes a stable internal CIDR for ingress, restrict to that range: `--forwarded-allow-ips '<CIDR>'`. Otherwise consider supplementing IP-based controls with user-agent or session-level signals. No code change recommended until the Azure ingress IP range is confirmed.

**Effort:** Low to investigate; mitigation depends on Azure network configuration.

---

### LOW-6 — `@require_GET` missing on the index view ✓ Fixed
**Severity:** Low

`@require_GET` added to `recipes/views.py` above the `@ratelimit` decorator on the `index` view. Non-GET requests to `/` now return HTTP 405, consistent with `search` and `health`.

---

### LOW-7 — HTMX loaded from external CDN (unpkg.com) ✓ Fixed
**Severity:** Low

HTMX 1.9.10 downloaded to `static/js/htmx.min.js` and served via WhiteNoise. The `unpkg.com` CDN script tag removed from `base.html`. `"https://unpkg.com"` removed from `CSP_SCRIPT_SRC` — `script-src` is now `'self'` only. All JavaScript (Alpine.js, HTMX, app.js) is self-hosted; there are no external script CDN dependencies in production.

---

## Informational Notes

### INFO-1 — CodeQL findings do not fail CI
CodeQL analysis uploads SARIF results to the GitHub Security tab but does not set `exit-code: 1`. This is an accepted design choice — persistent tracking without blocking every push. Security tab findings should be reviewed on a regular cadence.

### INFO-2 — Bandit uses `|| true` before inline Python parser
`bandit ... -o bandit-report.json || true` suppresses bandit's own exit code. The inline Python script reads the JSON and exits 1 on HIGH findings. If bandit crashes with a non-JSON error the Python script will also fail, so the gate still holds. The pattern is fragile but does not create a bypass.

### INFO-3 — `search_vector` field populated but unused in queries
`Recipe.search_vector` is a `SearchVectorField` with a GIN index. `RecipeManager.search()` uses `icontains` rather than `SearchQuery` / `SearchRank`. The field and index exist but provide no query benefit. If full-text search ranking is desired, migrate `search()` to use `SearchQuery`. Otherwise the field is safe dead weight.

### INFO-4 — No `Retry-After` header on 429 responses ✓ Fixed
`ratelimited` view updated: emits `logger.warning` with the client IP on every rate-limit hit (rate-limit spikes now visible in the application log stream), and sets `Retry-After: 60` on the response (60 seconds covers the longest per-minute window across all three endpoints).

### INFO-5 — Google Fonts loaded from external CDN
`fonts.googleapis.com` and `fonts.gstatic.com` are loaded unconditionally on every page, including in production. Every user's IP address is sent to Google's servers on page load. This is a privacy consideration, not a security vulnerability. If user privacy is a concern, Playfair Display and DM Sans can be self-hosted via the `google-webfonts-helper` tool and served via WhiteNoise, which would also allow removing `fonts.googleapis.com` from `CSP_STYLE_SRC` and `fonts.gstatic.com` from `CSP_FONT_SRC`.

### INFO-6 — `secrets: inherit` passes all secrets to security scanning jobs ✓ Fixed
`pipeline.yml` updated: `ci` and `security` jobs omit the `secrets:` key entirely (no secrets passed). The `deploy` job uses an explicit eight-entry `secrets:` mapping. `deploy.yml` now declares those eight secrets in its `on.workflow_call.secrets:` block with `required: true`. Azure credentials are no longer available to `pip-audit`, `bandit`, `CodeQL`, or `Trivy`.

---

## Fixed Findings

### M-1 — Tailwind CDN Play removed from production ✓ Fixed
Standalone Tailwind CLI downloads during the Docker builder stage, compiles `tailwind.output.css` in the final stage, then is deleted — it never ships at runtime. `base.html` uses `{% if debug %}` to load CDN Play only in local dev; production receives `<link rel="stylesheet" href="{% static 'css/tailwind.output.css' %}">` via WhiteNoise.

### M-2 — `'unsafe-inline'` removed from `style-src` CSP ✓ Fixed
All `style=""` inline attributes and `<style>` blocks moved to `app.css` as named classes. `style="display:none"` on Alpine.js `x-show` elements replaced with `x-cloak`. `[x-cloak] { display: none !important; }` in `app.css`. `CSP_STYLE_SRC` is now `('self', 'https://fonts.googleapis.com')` — no `unsafe-inline`.

### M-4 — ACR admin credentials replaced with OIDC ✓ Fixed
`docker/login-action` (admin creds) removed from the `build-and-push` job. `azure/login` (OIDC) authenticates to Azure; `az acr login --name` authenticates Docker to ACR using the short-lived OIDC token. `ACR_USERNAME` and `ACR_PASSWORD` secrets can be deleted from GitHub.

### LOW-2 — Alpine.js self-hosted, unpkg.com CDN eliminated ✓ Fixed
Alpine.js 3.14.1 downloaded to `static/js/alpinejs.min.js` and served via WhiteNoise. The `unpkg.com` CDN script tag removed from `base.html`.

### LOW-3 — Custom 429 handler for django-ratelimit ✓ Fixed
`RATELIMIT_VIEW = "recipes.views.ratelimited"` in `base.py`. The `ratelimited` view returns HTTP 429 with `content_type="text/plain"`.

### LOW-4 — `Permissions-Policy` header added ✓ Fixed
`django-permissions-policy` added to `requirements.txt` and `MIDDLEWARE`. `PERMISSIONS_POLICY` block in `base.py` disables accelerometer, camera, geolocation, gyroscope, magnetometer, microphone, payment, and USB.

### LOW-5 — `@require_GET` added to health view ✓ Fixed
`@require_GET` decorator added to `recipes/views.py`. Non-GET requests to `/health/` now return HTTP 405.

---

## Recommended Fix Order

1. ~~**LOW-6**~~ ✓ Done — `@require_GET` added to the `index` view.
2. ~~**LOW-7**~~ ✓ Done — HTMX self-hosted in `static/js/`; `https://unpkg.com` removed from `CSP_SCRIPT_SRC`.
3. **M-3** — Migrate Azure Storage to managed identity. Removes the last long-lived secret from GitHub. Requires Azure RBAC changes; no application logic changes.
4. **LOW-1** — Investigate Azure Container Apps ingress CIDR; restrict `--forwarded-allow-ips` if a stable range can be confirmed.
