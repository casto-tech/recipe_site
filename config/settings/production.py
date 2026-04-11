"""
Production settings — Azure Container Apps.
Inherits base settings and applies strict security hardening.
These settings are non-negotiable and must never be weakened.
"""

from .base import *  # noqa: F401, F403

DEBUG = False
ADMIN_ENABLED = False

# Remove django.contrib.admin from INSTALLED_APPS — eliminates the attack
# surface entirely. No admin tables loaded, no admin views registered,
# no admin URL can be mounted, all admin paths return HTTP 404.
INSTALLED_APPS = [app for app in INSTALLED_APPS if app != "django.contrib.admin"]  # noqa: F405

# ── HTTPS / Cookie Security ───────────────────────────────────────────────────
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 3600
CSRF_COOKIE_SECURE = True

# ── HSTS ──────────────────────────────────────────────────────────────────────
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# ── Content Security Policy (django-csp) ─────────────────────────────────────
MIDDLEWARE = MIDDLEWARE + ["csp.middleware.CSPMiddleware"]  # noqa: F405

_azure_blob_domain = (
    f"https://{AZURE_ACCOUNT_NAME}.blob.core.windows.net" if AZURE_ACCOUNT_NAME else ""  # noqa: F405  # noqa: F405
)

CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = (
    "'self'",
    "https://cdn.tailwindcss.com",
    "https://unpkg.com",
    "https://cdn.jsdelivr.net",
)
CSP_STYLE_SRC = (
    "'self'",
    "'unsafe-inline'",  # Required by Tailwind CDN play
    "https://cdn.tailwindcss.com",
)
_img_src = ["'self'", "data:", "https://picsum.photos"]
if _azure_blob_domain:
    _img_src.append(_azure_blob_domain)
CSP_IMG_SRC = tuple(_img_src)
CSP_FONT_SRC = ("'self'",)
CSP_CONNECT_SRC = ("'self'",)
CSP_FRAME_ANCESTORS = ("'none'",)
CSP_BASE_URI = ("'none'",)
CSP_FORM_ACTION = ("'self'",)
