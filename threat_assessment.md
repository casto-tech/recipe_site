# Threat Assessment — Recipe Site

**Date:** 2026-04-18
**Scope:** Application code, Django configuration, Docker image, CI/CD pipeline, Azure infrastructure
**Methodology:** Manual code review against OWASP Top 10, STRIDE, and cloud/pipeline security best practices

---

## Executive Summary

The application has a strong security baseline. There are **no Critical or High findings**. The attack surface is narrow — it is a read-only, authentication-free public site with a development-only admin interface. The codebase demonstrates deliberate security thinking: parameterised queries throughout, output escaping in all templates, layered rate limiting, brute-force lockout, a removed admin surface in production, OIDC instead of long-lived secrets, and SHA-pinned CI actions.

The findings below are genuine issues, not false positives.

| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 0 |
| Medium | 3 |
| Low | 6 |
| Informational | 5 |

---

## Findings

---

### MEDIUM-1 — Missing SRI on Tailwind CDN Script

**File:** [templates/base.html](templates/base.html) (line 9)
**OWASP:** A08 — Software and Data Integrity Failures

**Description:**
Alpine.js and HTMX are loaded with Subresource Integrity (SRI) hashes, which means a compromised CDN cannot inject malicious code for those libraries. However, the Tailwind CDN Play script has no SRI hash:

```html
<!-- Protected with SRI -->
<script defer src="https://unpkg.com/alpinejs@3.14.1/..."
  integrity="sha384-l8f0VcPi/..." crossorigin="anonymous"></script>

<!-- NOT protected — no integrity attribute -->
<script src="https://cdn.tailwindcss.com"></script>
```

Tailwind CDN Play is a JavaScript runtime that reads the `tailwind.config` object and injects `<style>` tags. If `cdn.tailwindcss.com` were compromised, the attacker's script would execute with full DOM access on every page load. The CSP `script-src` whitelist permits this domain, so CSP would not block such a response.

SRI cannot be applied to Tailwind CDN Play as-is because it is a dynamic script (it evaluates `tailwind.config` at runtime and produces different output on each request), making a stable hash impossible to pre-compute.

**Remediation:** Compile Tailwind to a static CSS bundle at build time and serve it via WhiteNoise. This eliminates the CDN dependency entirely, removes `cdn.tailwindcss.com` from `script-src`, and also resolves MEDIUM-2.

---

### MEDIUM-2 — `style-src 'unsafe-inline'` in Production CSP

**File:** [config/settings/production.py](config/settings/production.py) (line 48–53)
**OWASP:** A05 — Security Misconfiguration

**Description:**
The Content Security Policy includes `'unsafe-inline'` in `style-src`, which is required by Tailwind CDN Play (it injects `<style>` tags at runtime). This means any CSS injection reaching the DOM can execute. CSS injection enables:

- UI redirection attacks (overlaying fake buttons/forms)
- Data exfiltration via attribute selectors (e.g., leaking CSRF tokens character-by-character)
- Clickjacking-adjacent attacks that bypass the `frame-ancestors 'none'` directive if CSS can fake UI chrome

The `frame-ancestors 'none'` and `X-Frame-Options: DENY` directives are correctly set and remain effective. The risk is limited to CSS injection via stored content — which requires an admin to enter malicious data and the admin not existing in production. The residual risk is low in practice, but `'unsafe-inline'` in `style-src` is a known-weak posture.

**Remediation:** Same as MEDIUM-1 — compile Tailwind to a static bundle. Once Tailwind is no longer injecting `<style>` tags, `'unsafe-inline'` can be removed from `style-src`.

---

### MEDIUM-3 — Storage Account Shared Key Has Excessive Privilege

**File:** [config/settings/base.py](config/settings/base.py) (line 116)
**OWASP:** A01 — Broken Access Control (over-privileged credential)

**Description:**
Recipe images are stored in Azure Blob Storage using the storage account's primary key (`AZURE_STORAGE_ACCOUNT_KEY`). A shared key grants full access to the entire storage account — read, write, delete on all containers and all blobs, including the ability to generate SAS tokens for any resource and access management operations.

If this key is leaked (e.g., via a misconfigured log, a compromised GitHub secret, or a Container App environment variable dump), an attacker would have unrestricted access to the storage account, not just the `media` container.

This is documented as known technical debt in [infrastructure_documentation.md](infrastructure_documentation.md).

**Remediation (preferred):** Enable a system-assigned Managed Identity on the Container App and assign it the `Storage Blob Data Contributor` role scoped to the `media` container only. Update `django-storages` configuration to use `AZURE_USE_SERVICE_PRINCIPAL=False` with `AZURE_MANAGED_IDENTITY_CLIENT_ID`. Eliminates the credential entirely.

**Remediation (acceptable short-term):** Replace the account key with a User Delegation SAS token scoped to `svc=b&srt=o&sp=rwdlac&sv=...` on the `media` container only. Set a short expiry and rotate regularly.

---

### LOW-1 — SSRF Validator Mismatch: Server Does Not Fetch `image_url`

**File:** [recipes/validators.py](recipes/validators.py), [recipes/models.py](recipes/models.py) (line 35)
**OWASP:** A10 — Server-Side Request Forgery

**Description:**
The `validate_no_private_url` validator rejects URLs pointing to private/loopback/reserved IPs, with the intent of preventing SSRF. However, examining the entire codebase, the server never fetches `image_url`. It is only rendered as an `<img src="...">` attribute in the browser. The SSRF threat it is designed to prevent does not exist in the current code.

As a result, the validator provides false security confidence while not fully addressing the actual risk. The actual risk is that a trusted admin could store a URL that causes **visitors' browsers** to make a request to a third-party server (e.g., a tracking pixel). This is a different threat model — client-side request, not server-side.

Additionally, the validator has a gap: it correctly blocks IP literals but does not block domain names that resolve to private IPs (DNS rebinding). A domain like `metadata.attacker.com` configured to resolve to `169.254.169.254` would pass validation. This gap is irrelevant against the current threat (no server-side fetch), but would be exploitable if a server-side fetch were ever added.

**Remediation:**
1. Update the validator's docstring to reflect the actual threat it mitigates (stored third-party URL exposure, not SSRF).
2. If a server-side image fetch feature is ever added, implement a DNS-resolving check (resolve the hostname to an IP and validate the resolved IP, not just the literal) before making any outbound request.

---

### LOW-2 — Alpine.js Click Handler Vulnerable to Tag Name Injection (Dev Only)

**File:** [templates/recipes/index.html](templates/recipes/index.html) (line 409)
**OWASP:** A03 — Injection (Stored XSS)

**Description:**
Tag names and slugs are rendered directly into an Alpine.js `@click` expression inside an HTML attribute:

```html
@click="selected='{{ tag.slug }}'; label='{{ tag.name }}'; open=false; ..."
```

Django's auto-escaping converts `"` to `&quot;` (protecting the attribute boundary) but converts `'` to `&#x27;`. The HTML parser decodes `&#x27;` back to a literal `'` when passing the attribute value to Alpine.js for evaluation. Alpine.js then evaluates the string as JavaScript.

A tag name containing `x'; alert(document.cookie); var z='` would result in Alpine.js executing:

```javascript
selected='...'; label='x'; alert(document.cookie); var z=''; open=false;
```

**This is exploitable only if a malicious user can create tags**, which requires admin access. The admin is completely absent in production (`ADMIN_ENABLED=False`, `django.contrib.admin` removed from `INSTALLED_APPS`). This is a dev-environment-only risk from a trusted admin account. It is documented here because it represents a design pattern that should not be replicated if the site ever grows public write paths.

**Remediation:** Use `{{ tag.name|escapejs }}` and `{{ tag.slug|escapejs }}` in the Alpine.js expression context, or better, move the tag data to a `data-tag` attribute and read it in the event handler:

```html
<button type="button"
  data-slug="{{ tag.slug }}"
  data-name="{{ tag.name }}"
  @click="selected = $el.dataset.slug; label = $el.dataset.name; open = false; ...">
```

This approach is immune to injection because the data is read from separate DOM attributes, not evaluated as expressions.

---

### LOW-3 — Rate Limit Response Code Is 403 Instead of 429

**File:** [recipes/views.py](recipes/views.py) (lines 19, 35, 57)
**OWASP:** A05 — Security Misconfiguration (non-standard behaviour)

**Description:**
`django-ratelimit` with `block=True` raises `Forbidden` (HTTP 403) when the rate limit is exceeded, rather than `Too Many Requests` (HTTP 429). This is the library's default behaviour.

HTTP 429 is the correct status code for rate limiting (RFC 6585). Returning 403 is misleading: it implies the client is permanently forbidden rather than temporarily throttled. Monitoring tools and clients that inspect status codes for retry logic may behave incorrectly.

Note that `django-axes` correctly returns 429 for brute-force lockouts (as verified by `test_admin_lockout_after_failed_attempts`).

**Remediation:** Create a custom handler for `django_ratelimit.exceptions.Ratelimited` in Django's exception middleware, or set a custom `RATELIMIT_VIEW` in settings that returns `HttpResponse(status=429)`.

---

### LOW-4 — `Permissions-Policy` Header Not Set

**File:** [config/settings/base.py](config/settings/base.py), [config/settings/production.py](config/settings/production.py)
**OWASP:** A05 — Security Misconfiguration

**Description:**
The application sets `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, HSTS, and a full CSP, but does not set a `Permissions-Policy` header. This header restricts access to browser APIs (camera, microphone, geolocation, payment, USB, etc.). While the recipe site has no legitimate need for any of these APIs, not setting the header leaves them at their browser defaults, which could be exploited by a successfully injected script.

**Remediation:** Add a restrictive `Permissions-Policy` header via Django middleware or directly in the CSP configuration. A suitable default for this site:

```python
# In production.py or base.py
SECURE_PERMISSIONS_POLICY = {
    "camera": [],
    "microphone": [],
    "geolocation": [],
    "payment": [],
    "usb": [],
    "fullscreen": ["self"],
}
```

Django does not have built-in support for this header; use `django-permissions-policy` (a small, well-maintained package) or add it via a custom middleware `process_response`.

---

### LOW-5 — Health Endpoint Accepts All HTTP Methods

**File:** [recipes/views.py](recipes/views.py) (line 57), [recipes/urls.py](recipes/urls.py)
**OWASP:** A05 — Security Misconfiguration

**Description:**
The `index` and `search` views are decorated with `@require_GET`, but the `health` view is not:

```python
@ratelimit(key="ip", rate="60/m", block=True)
def health(request):
    return JsonResponse({"status": "ok"})
```

A `POST`, `PUT`, `DELETE`, or `OPTIONS` request to `/health/` returns HTTP 200 with `{"status": "ok"}`. RFC-compliant health endpoints should only respond to GET (and optionally HEAD). This is a minor non-conformance rather than an exploitable vulnerability.

**Remediation:**

```python
@require_GET
@ratelimit(key="ip", rate="60/m", block=True)
def health(request):
    return JsonResponse({"status": "ok"})
```

---

### LOW-6 — `CONN_MAX_AGE` Creates a Credential Rotation Gap

**File:** [config/settings/base.py](config/settings/base.py) (line 83)
**OWASP:** A07 — Identification and Authentication Failures

**Description:**
`CONN_MAX_AGE = 60` enables persistent database connections with a 60-second maximum lifetime. If the PostgreSQL password (`DB_PASSWORD`) is rotated, existing Gunicorn workers will continue to use the old connection for up to 60 seconds before it is closed and a new connection (with the new credentials) is established.

This is a minor operational gap during credential rotation, not an ongoing vulnerability.

**Remediation:** When rotating `DB_PASSWORD`, perform a rolling Container App restart after updating the environment variable. Alternatively, set `CONN_MAX_AGE = 0` to disable persistent connections if credential rotation SLAs require immediate enforcement. `CONN_HEALTH_CHECKS = True` (already set) will catch stale connections but does not shorten the gap window.

---

### INFO-1 — Search Uses `icontains` Instead of Configured Full-Text Search Index

**File:** [recipes/managers.py](recipes/managers.py) (lines 31–36), [recipes/models.py](recipes/models.py) (line 45)
**Category:** Performance / Operational Risk

**Description:**
The `Recipe` model includes a `SearchVectorField` with a GIN index:

```python
search_vector = SearchVectorField(null=True, blank=True)
indexes = [GinIndex(fields=["search_vector"])]
```

However, `RecipeManager.search()` uses `__icontains` (LIKE `%query%`) queries, not PostgreSQL full-text search against `search_vector`. The GIN index is unused:

```python
qs.filter(
    Q(title__icontains=query)
    | Q(tags__name__icontains=query)
    | Q(ingredients__icontains=query)
)
```

`icontains` queries do full table scans on the `title`, `tags__name`, and `ingredients` fields. On a small recipe collection this is harmless, but it means the GIN index exists but provides no benefit — it occupies storage and slows down writes.

This is not a security finding. It becomes a security-adjacent concern if a DoS via expensive search queries is a threat model (an attacker could send many concurrent queries with patterns that maximise scan time).

**Remediation:** Either implement `SearchVector`/`SearchQuery` against the `search_vector` field, or remove the `SearchVectorField` and `GinIndex` to avoid maintaining dead infrastructure.

---

### INFO-2 — No `robots.txt`

**File:** N/A — file does not exist
**Category:** Information Exposure

**Description:**
There is no `robots.txt` at the site root. All paths — including the health endpoint, future admin-adjacent paths, and any debug or staging variants — are freely crawlable and indexable by search engines.

For a personal recipe site with no sensitive paths, this is low impact. If the site ever has staging environments on the same domain, or paths that should not be indexed, `robots.txt` becomes important.

**Remediation:** Add a minimal `robots.txt` served via WhiteNoise:

```
User-agent: *
Disallow: /health/
Disallow: /search/
Allow: /
```

---

### INFO-3 — Container App Environment Variables Hold Secrets Directly

**File:** [infrastructure_documentation.md](infrastructure_documentation.md), Azure Container App configuration
**Category:** Secrets Management

**Description:**
Sensitive values (`DJANGO_SECRET_KEY`, `DB_PASSWORD`, `AZURE_STORAGE_ACCOUNT_KEY`) are stored as plain environment variables on the Azure Container App. Any identity with `Contributor` or `Reader` access to the resource group can view these values in the Azure Portal or via the Azure CLI.

This is common practice for Container Apps but is weaker than referencing secrets from Azure Key Vault. Key Vault provides audit logging of each secret access, independent rotation, and access policy control decoupled from the resource group RBAC.

**Remediation:** Store secrets in Azure Key Vault and reference them in the Container App as Key Vault references. Container Apps support this natively:

```bash
az containerapp secret set \
  --name <APP_NAME> \
  --resource-group <RG> \
  --secrets "django-secret-key=keyvaultref:<KEY_VAULT_SECRET_URI>,identityref:<MANAGED_IDENTITY_RESOURCE_ID>"
```

---

### INFO-4 — No CSP Violation Reporting Endpoint

**File:** [config/settings/production.py](config/settings/production.py)
**Category:** Monitoring / Observability

**Description:**
The Content Security Policy has no `report-uri` or `report-to` directive. CSP violations (e.g., a blocked inline script or an unexpected external resource load) are silently discarded — they appear only in the browser's DevTools console of the user who experiences them.

Without reporting, a real XSS attack that is partially blocked by CSP would leave no server-side trace.

**Remediation:** Add a `report-uri` directive pointing to a logging endpoint. A free tier at [report-uri.com](https://report-uri.com) or a self-hosted endpoint that writes to Azure Monitor would provide visibility:

```python
CSP_REPORT_URI = "/csp-report/"
# or use an external service: "https://your-id.report-uri.com/r/d/csp/enforce"
```

---

### INFO-5 — `SECURE_REFERRER_POLICY` Sends Origin to External CDNs

**File:** [config/settings/base.py](config/settings/base.py) (line 141)
**Category:** Privacy / Information Disclosure

**Description:**
`SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"` sends the origin (e.g., `https://yourapp.azurecontainerapps.io`) as the `Referer` header on all cross-origin HTTPS requests. Every request to Tailwind CDN, unpkg, and Google Fonts includes this referrer.

For a public-facing site where the domain is not sensitive, this is not a problem. If the Container App domain changes, or if the site is accessed via a private/internal hostname that should not be disclosed to third parties, this setting would leak it.

**Remediation:** No immediate action required. If the domain is ever sensitive, switch to `"same-origin"` or `"no-referrer"`.

---

## What Is Working Well

The following controls are implemented correctly and represent genuine defense-in-depth:

| Control | Implementation | Notes |
|---------|---------------|-------|
| SQL Injection | Django ORM with parameterised queries throughout | No raw SQL anywhere in the codebase |
| XSS — templates | Django auto-escaping + `\|escapejs` on all JSON blobs | `card_detail.html` uses `x-text` (not `x-html`) for all dynamic content |
| XSS — headers | `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, strict CSP | Prevents MIME confusion and clickjacking |
| CSRF | Django `CsrfViewMiddleware` active; only GET endpoints are public | No state-changing operations exposed publicly |
| Brute force | `django-axes`: 5-attempt lockout, 1-hour cooldown, per-IP | Returns HTTP 429 on lockout |
| Rate limiting | `django-ratelimit`: 60/min index, 30/min search, 60/min health | Reads real client IP via `--forwarded-allow-ips '*'` |
| Admin removal | `django.contrib.admin` removed from `INSTALLED_APPS` in production | Not just URL-blocked — entirely absent from the process |
| Admin smoke test | Deploy pipeline verifies `/management/` returns 404 after every deploy | Automated enforcement |
| HTTPS | `SECURE_SSL_REDIRECT`, 1-year HSTS with preload, proxy header trusted | Azure SSL termination handled correctly |
| Secure cookies | Secure, HttpOnly, SameSite=Strict, 1-hour expiry | All four attributes set |
| Image upload validation | Extension + size + Pillow `img.verify()` + format-matches-extension checks | Prevents polyglot file uploads |
| SSRF surface | No server-side URL fetching; `image_url` is admin-only | Narrow attack surface |
| Secrets in CI | OIDC replaces `AZURE_CREDENTIALS`; no long-lived Azure secret in GitHub | Short-lived token per run |
| Supply chain | All GitHub Actions pinned to full commit SHAs | Prevents tag-push supply chain attacks |
| SRI | Alpine.js and HTMX loaded with `integrity` + `crossorigin` attributes | CDN compromise cannot inject script for these two libraries |
| Container hardening | Multi-stage build, non-root user, no build tools in final image, OS patched during build | Minimal attack surface in container |
| Secret bake prevention | `SECRET_KEY` is a build-arg placeholder; real value injected at runtime only | Not present in image layers |
| Structured logging | JSON to stdout; no file writes; `AXES_VERBOSE=False` | No sensitive data in logs |
| CI security gates | pip-audit (CVEs), bandit (SAST), Trivy (container CVEs), CodeQL | Four independent gates before deploy |
| Least privilege | All GitHub Actions workflows default to `permissions: {}` | Per-job grant only |
| Concurrency control | Deploy group prevents parallel deploys racing on Container App | Operational safety |

---

## Risk Register Summary

| ID | Title | Severity | Effort to Fix |
|----|-------|----------|--------------|
| MEDIUM-1 | Missing SRI on Tailwind CDN | Medium | High (requires compiling Tailwind) |
| MEDIUM-2 | `style-src 'unsafe-inline'` in CSP | Medium | High (same fix as MEDIUM-1) |
| MEDIUM-3 | Storage account shared key | Medium | Medium (Managed Identity setup) |
| LOW-1 | SSRF validator / threat mismatch | Low | Low (comment update + future note) |
| LOW-2 | Alpine.js tag name injection (dev only) | Low | Low (`data-*` attribute refactor) |
| LOW-3 | Rate limit returns 403 instead of 429 | Low | Low (custom exception handler) |
| LOW-4 | Missing `Permissions-Policy` header | Low | Low (one package + config) |
| LOW-5 | Health endpoint accepts all methods | Low | Trivial (add `@require_GET`) |
| LOW-6 | Credential rotation gap (`CONN_MAX_AGE`) | Low | Low (restart procedure) |
| INFO-1 | GIN index unused (icontains vs FTS) | Info | Medium |
| INFO-2 | No `robots.txt` | Info | Trivial |
| INFO-3 | Secrets in env vars vs Key Vault | Info | Medium |
| INFO-4 | No CSP reporting endpoint | Info | Low |
| INFO-5 | Referrer leaks origin to CDNs | Info | Trivial |

### Recommended fix order

1. **LOW-5** — Add `@require_GET` to `health` view. One line, zero risk.
2. **LOW-3** — Custom 429 handler for `django-ratelimit`. Small change, correct HTTP semantics.
3. **LOW-2** — Refactor tag buttons to use `data-*` attributes. Eliminates the injection class entirely.
4. **LOW-4** — Add `django-permissions-policy`. One package, one settings block.
5. **MEDIUM-3** — Migrate to Managed Identity for blob storage. Most impactful near-term security improvement.
6. **MEDIUM-1 + MEDIUM-2** — Compile Tailwind to static CSS. Resolves both Medium findings and the Tailwind CDN availability dependency in one change.
