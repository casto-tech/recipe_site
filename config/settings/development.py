"""
Development settings — local only.
Inherits all base settings; only overrides what differs for local dev.
"""

from .base import *  # noqa: F401, F403

DEBUG = True

ADMIN_ENABLED = True

# ── Admin Customisation ───────────────────────────────────────────────────────
ADMIN_SITE_HEADER = "Recipe Book — Local Admin"
ADMIN_SITE_TITLE = "Recipe Book Dev"
ADMIN_INDEX_TITLE = "Local Development Only — Not Available in Production"

# ── Email ─────────────────────────────────────────────────────────────────────
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
