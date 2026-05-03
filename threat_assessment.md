# Threat Assessment — Recipe Site
**Date:** 2026-05-03  
**Assessor:** Claude Code (claude-sonnet-4-6)  
**Branch assessed:** `security`  
**Scope:** Django application code, templates, CI/CD pipeline, Dockerfile, GitHub Actions workflows, Azure infrastructure configuration  
**Methodology:** OWASP Top 10, STRIDE  
**Rating dimensions:** Severity (overall risk) · Impact (consequence if exploited) · Likelihood (probability of exploitation in practice)

---

## Executive Summary

No Critical or High severity findings. The security posture has materially strengthened across every layer since the initial assessment: all CDN JavaScript dependencies are now self-hosted, the CSP `script-src` is locked to `'self'` only with no `unsafe-inline` anywhere, ACR authentication uses OIDC, GitHub Actions secrets are scoped to only the jobs that need them, rate-limit responses carry the correct HTTP 429 with a `Retry-After` header and a log entry, and all three public views enforce `@require_GET`. One Medium finding (Azure Storage Account Key) and one Low finding (Gunicorn forwarded-allow-ips) remain open.

**Finding summary:**

| ID     | Severity      | Impact  | Likelihood | Title                                           | Status    |
|--------|---------------|---------|------------|-------------------------------------------------|-----------|
| M-3    | Medium        | High    | Low        | Azure Storage Account Key as long-lived secret  | Open      |
| LOW-1  | Low           | Medium  | Low        | Gunicorn `--forwarded-allow-ips '*'`            | Open      |
| INFO-1 | Informational | Low     | —          | CodeQL findings do not fail CI                  | Accepted  |
| INFO-2 | Informational | Low     | —          | Bandit uses `\|\| true` before inline parser    | Accepted  |
| INFO-3 | Informational | Low     | —          | `search_vector` field unused in queries         | Note      |
| INFO-4 | Informational | Low     | —          | Google Fonts loaded from external CDN           | Note      |
| INFO-5 | Informational | Low     | Low        | No CSP violation reporting endpoint             | Note      |
| INFO-6 | Informational | Low     | Low        | Development container runs as root              | Note      |

---

## OWASP Top 10 Assessment

### A01 — Broken Access Control
**Rating: Low Risk**

The application is publicly read-only with no user-facing authentication. `@require_GET` is enforced on all three public views (`index`, `search`, `health`). The Django admin is removed from `INSTALLED_APPS` in production — no admin tables, views, or URLs exist at runtime; `/management/` returns HTTP 404. A smoke test in the deploy pipeline asserts this after every deployment. CSRF middleware is active for all state-changing operations. `form-action: 'self'` in the CSP prevents cross-origin form submission. `frame-ancestors: 'none'` blocks clickjacking. No user-controlled URL routing exists in the application.

### A02 — Cryptographic Failures
**Rating: Low Risk**

HTTPS enforced via `SECURE_SSL_REDIRECT = True` and Azure Container Apps TLS termination. `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")` trusts the forwarded protocol header from any upstream — this is required for Azure's SSL termination but depends on Azure correctly stripping this header from client requests (see LOW-1 for related proxy-trust risk). HSTS is set to one year with `includeSubDomains` and `preload`. Session and CSRF cookies are `Secure`, `HttpOnly`, and `SameSite=Strict`. `SECRET_KEY` is injected at runtime; only a placeholder is baked into the image during `collectstatic`. No sensitive data is stored in the application database.

### A03 — Injection
**Rating: Low Risk**

All database access uses the Django ORM exclusively — no raw SQL. `SearchForm` validates the `tag` query parameter with `required=False` and a regex restricted to `[a-z0-9\-]+`. The text search query is now handled entirely client-side (Alpine.js `String.includes()`) — it is never sent to the server as a query parameter and never reaches any database query. Recipe titles rendered into `data-title` HTML attributes use Django's default auto-escaping. Recipe data embedded in `<script type="application/json">` uses `|escapejs` on every string value and is read with `JSON.parse()` — type `application/json` prevents browser execution. The `format_html` helper in admin escapes `image_url` before rendering a thumbnail. Image uploads are validated by extension, size (5 MB cap), and Pillow content inspection — extension/content mismatch is detected and rejected. The SSRF validator on `image_url` uses Python's `ipaddress` module to reject all private, loopback, link-local, multicast, and reserved IP ranges, and rejects `localhost` by hostname before IP parsing.

### A04 — Insecure Design
**Rating: Low Risk**

The application stores only recipe content — no PII, no payment data, no credentials. Attack surface is minimal: three public GET endpoints. Rate limiting covers all three. Image URL values are stored and rendered as `<img src>` attributes — the HTTP fetch goes from the user's browser, not the server, so `image_url` is not an SSRF vector at request time. The admin interface only uploads images into Azure Blob Storage; it never fetches arbitrary URLs server-side.

### A05 — Security Misconfiguration
**Rating: Low Risk**

`DEBUG = False` in production. `ALLOWED_HOSTS` enforced. `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, and `Permissions-Policy` (disabling camera, geolocation, microphone, payment, and five others) are all set. The CSP is tight:

| Directive       | Value                                     | Notes                                      |
|-----------------|-------------------------------------------|--------------------------------------------|
| `default-src`   | `'self'`                                  | Baseline for all resource types            |
| `script-src`    | `'self'`                                  | All JS self-hosted; no CDN, no unsafe-inline |
| `style-src`     | `'self'`, `fonts.googleapis.com`          | No `unsafe-inline`                         |
| `img-src`       | `'self'`, `data:`, Azure Blob domain      | Blob domain added dynamically from env var |
| `font-src`      | `'self'`, `fonts.gstatic.com`             |                                            |
| `connect-src`   | `'self'`                                  | HTMX XHR requests stay on-origin          |
| `frame-ancestors` | `'none'`                                | Clickjacking prevention                    |
| `base-uri`      | `'none'`                                  | Prevents `<base>` tag injection            |
| `form-action`   | `'self'`                                  | Forms submit only to this origin           |

In development, Tailwind CDN Play is loaded from `cdn.tailwindcss.com` via the `{% if debug %}` branch. This is intentional and isolated to development; CSP middleware is not active in development.

### A06 — Vulnerable and Outdated Components
**Rating: Low Risk**

`pip-audit` blocks the pipeline on any unfixed CVE in installed packages. One CVE (`CVE-2026-3219` in pip itself) is suppressed with `--ignore-vuln` and a comment flagging it for removal once pip ships a patch. Trivy scans the Docker image and blocks on fixable HIGH/CRITICAL OS-level CVEs. Dependabot opens weekly PRs for Python dependencies and GitHub Actions. All Actions are pinned to full commit SHAs. `apt-get upgrade -y` runs in both Dockerfile stages at build time.

### A07 — Identification and Authentication Failures
**Rating: Low Risk**

No public login surface exists. Admin login (development only) is protected by `django-axes`: five failures triggers a one-hour IP lockout. `AXES_RESET_ON_SUCCESS = True` and `AXES_VERBOSE = False` (sensitive request data is never logged). Auth password validators enforce minimum length, common password rejection, and user-attribute similarity checks.

### A08 — Software and Data Integrity Failures
**Rating: Low Risk**

All JavaScript — Alpine.js 3.14.1, HTMX 1.9.10, and `app.js` — is self-hosted and served by WhiteNoise with content-hashed filenames. Tailwind CSS is compiled from source at Docker build time by the standalone CLI binary, which is then deleted. There are no runtime CDN script dependencies. GitHub Actions are pinned to commit SHAs. OIDC federated credentials are used for both Azure login and ACR authentication; no long-lived `AZURE_CREDENTIALS` JSON or ACR admin password is stored in GitHub. The `ci` and `security` pipeline jobs receive no secrets; only the `deploy` job receives the eight secrets it explicitly needs.

### A09 — Security Logging and Monitoring Failures
**Rating: Low Risk**

Structured JSON logging writes to stdout, captured by Azure Monitor. `django.request` and `django.security` log at WARNING. `axes` logs lockout events. The `ratelimited` view emits a `WARNING` with the client IP and returns `Retry-After: 60`. The IP logged may be spoofed when `--forwarded-allow-ips '*'` is active (see LOW-1), which limits forensic reliability of rate-limit log entries.

### A10 — Server-Side Request Forgery (SSRF)
**Rating: Low Risk**

`validate_no_private_url` in `recipes/validators.py` rejects all RFC-1918, loopback, link-local, multicast, and unspecified addresses, and rejects `localhost` and `localhost.localdomain` explicitly. Only HTTP and HTTPS schemes are permitted. Applied at the model level. The stored URL is rendered as `<img src>` in the browser — the browser fetches the image, not the server. No server-side HTTP client fetches any stored URL.

---

## STRIDE Analysis

| Threat              | Controls in place                                                                                                    | Residual gap                                                        |
|---------------------|----------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------|
| **Spoofing**        | OIDC federated credentials; django-axes IP lockout; CSRF; `SameSite=Strict` cookies; `form-action: 'self'`          | X-Forwarded-For spoofable; rate-limit log IPs unreliable (LOW-1)   |
| **Tampering**       | CSRF enforced; ORM parameterised queries; image upload validated; `escapejs` in JSON; `format_html` in admin; SRI via self-hosting | None significant                                             |
| **Repudiation**     | Structured JSON logging; axes lockout events; rate-limit events logged with IP                                       | Logged IPs may be spoofed (LOW-1)                                  |
| **Info Disclosure** | `DEBUG=False`; no stack traces; generic error pages; no sensitive data in DB; `AXES_VERBOSE=False`; `Retry-After` header only | None significant                                               |
| **DoS**             | Rate limiting (60/m index, 30/m search, 60/m health); HTTP 429 with `Retry-After`; DB-free health endpoint           | IP-based rate limiting bypassable via X-Forwarded-For spoofing (LOW-1) |
| **EoP**             | Non-root container in production; admin removed from `INSTALLED_APPS`; no privilege-escalation paths in code         | Azure Storage key grants full blob access if compromised (M-3)     |

---

## Open Findings

---

### M-3 — Azure Storage Account Key stored as a long-lived GitHub secret
**Severity:** Medium | **Impact:** High | **Likelihood:** Low

**Impact detail:** `AZURE_ACCOUNT_KEY` grants unrestricted read, write, and delete on all containers in the storage account. A compromised key allows an attacker to exfiltrate all uploaded recipe images, overwrite them with malicious content, or delete them entirely. Keys do not expire and cannot be scoped to a single container.

**Likelihood detail:** Exploitation requires compromise of a GitHub repository secret, which is a well-protected surface. The key is not logged, not exposed in responses, and not printed during builds. Likelihood is low but impact is high enough to warrant a Medium severity.

**Location:** `config/settings/base.py` → `AZURE_ACCOUNT_KEY`; GitHub Actions secret `AZURE_STORAGE_ACCOUNT_KEY`

**Fix:** Assign a managed identity to the Azure Container App and grant it `Storage Blob Data Contributor` on the media container only. `django-storages` picks up `DefaultAzureCredential` automatically when no key is configured. Remove `AZURE_ACCOUNT_KEY` from `base.py` and from GitHub secrets. Grant the OIDC service principal the same RBAC role for CI use.

**Effort:** Medium — Azure RBAC assignment and one settings change; no application logic changes.

---

### LOW-1 — Gunicorn `--forwarded-allow-ips '*'` enables proxy-header spoofing
**Severity:** Low | **Impact:** Medium | **Likelihood:** Low

**Impact detail:** With `--forwarded-allow-ips '*'`, Gunicorn trusts `X-Forwarded-For` from any upstream and sets `REMOTE_ADDR` accordingly. `django-ratelimit` and `django-axes` both key on `REMOTE_ADDR`. An attacker who can inject or forge `X-Forwarded-For` can cycle through arbitrary IPs to bypass rate limiting on all three endpoints and bypass admin brute-force lockouts (development only). The same trust model applies to `X-Forwarded-Proto`: Django accepts this header from any upstream to determine whether the request was HTTPS, which is required for Azure's SSL termination but would allow a client to claim HTTPS over a plain HTTP connection if Azure does not sanitise the header. Rate-limit log entries are also unreliable because logged IPs reflect the (potentially forged) `X-Forwarded-For` value.

**Likelihood detail:** Exploitation requires the ability to control or inject `X-Forwarded-For` headers. Azure Container Apps' ingress should normally handle this, but the specific header-stripping behaviour of Azure's ingress for external requests is not formally documented. Likelihood is low but non-zero.

**Location:** `entrypoint.sh` → `--forwarded-allow-ips '*'`

**Fix:** Restrict `--forwarded-allow-ips` to the Azure Container Apps ingress CIDR once that range is confirmed. If no stable CIDR is available, document the accepted risk and consider supplementing IP-based controls with other signals.

**Effort:** Low to investigate; mitigation depends on Azure network configuration.

---

## Informational Notes

### INFO-1 — CodeQL findings do not fail CI
**Severity:** Informational | **Impact:** Low | **Likelihood:** —

CodeQL uploads SARIF results to the GitHub Security tab but does not set `exit-code: 1`. This is an accepted design choice — persistent tracking without blocking every push. Security tab findings should be reviewed regularly.

---

### INFO-2 — Bandit uses `|| true` before inline Python parser
**Severity:** Informational | **Impact:** Low | **Likelihood:** —

`bandit ... -o bandit-report.json || true` suppresses bandit's exit code. The inline Python reads the JSON and exits 1 on HIGH findings. If bandit crashes with a non-JSON error the Python script also fails, so the gate still holds. The pattern is fragile but does not create a bypass.

---

### INFO-3 — `search_vector` field populated but unused in queries
**Severity:** Informational | **Impact:** Low | **Likelihood:** —

`Recipe.search_vector` is a `SearchVectorField` with a GIN index. `RecipeManager.search()` filters by `icontains` rather than `SearchQuery` / `SearchRank`. The field and index exist but are never written to or queried, consuming storage and incurring index-maintenance overhead on every write. Remove the field and migration to clean this up, or migrate `search()` to use `SearchQuery` if ranked full-text search is desired.

---

### INFO-4 — Google Fonts loaded from external CDN on every page load
**Severity:** Informational | **Impact:** Low | **Likelihood:** High

`fonts.googleapis.com` and `fonts.gstatic.com` are loaded unconditionally, including in production. Every user's IP address and browser user-agent are sent to Google's infrastructure on every page load. This is a privacy consideration, not a direct security vulnerability. Self-hosting Playfair Display and DM Sans via WhiteNoise would eliminate this dependency and allow removing `fonts.googleapis.com` from `CSP_STYLE_SRC` and `fonts.gstatic.com` from `CSP_FONT_SRC`, tightening the policy further.

---

### INFO-5 — No CSP violation reporting endpoint
**Severity:** Informational | **Impact:** Low | **Likelihood:** Low

The CSP has no `report-uri` or `report-to` directive. Violations are silently blocked by the browser — there is no signal that an injection attempt was stopped by the CSP. Adding a `report-to` endpoint (even a third-party service) would provide early warning of active injection attempts or misconfigured resources without weakening the policy.

---

### INFO-6 — Development container runs as root
**Severity:** Informational | **Impact:** Low | **Likelihood:** Low

`docker-compose.yml` sets `user: root` for the web service so that volume-mounted host files (owned by the developer's user) are readable inside the container. In production, the container runs as the non-root `appuser`. The development-only root posture means a compromised development dependency or malicious package would have root access to the container filesystem. This is a common trade-off in volume-mounted dev setups and is not a production risk.

---

## Previously Fixed Findings

| ID     | Title                                              | Fixed In              |
|--------|----------------------------------------------------|-----------------------|
| M-1    | Tailwind CDN Play in production                    | Dockerfile + base.html|
| M-2    | `'unsafe-inline'` in `style-src` CSP              | production.py + app.css |
| M-4    | ACR admin credentials in deploy pipeline           | deploy.yml            |
| LOW-2  | Alpine.js loaded from unpkg.com CDN                | static/js/alpinejs.min.js |
| LOW-3  | No custom 429 handler for rate limiting            | views.py              |
| LOW-4  | `Permissions-Policy` header absent                 | base.py + requirements.txt |
| LOW-5  | `@require_GET` missing on health view              | views.py              |
| LOW-6  | `@require_GET` missing on index view               | views.py              |
| LOW-7  | HTMX loaded from unpkg.com CDN                     | static/js/htmx.min.js |
| INFO-A | No `Retry-After` header on 429 responses           | views.py              |
| INFO-B | `secrets: inherit` passes all secrets to CI jobs   | pipeline.yml + deploy.yml |

---

## Recommended Fix Order

1. **M-3** — Migrate Azure Storage to managed identity. Removes the only remaining long-lived secret. Requires Azure RBAC changes; no application code changes.
2. **LOW-1** — Investigate Azure Container Apps ingress CIDR; restrict `--forwarded-allow-ips` if a stable range can be confirmed.
3. **INFO-4** — Self-host Google Fonts. Same pattern as Alpine.js and HTMX: download the font files, serve via WhiteNoise, tighten the CSP.
4. **INFO-5** — Add a `report-to` CSP directive to gain visibility into blocked injection attempts.
