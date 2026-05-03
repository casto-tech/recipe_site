"""
Development settings — local only.
Inherits all base settings; only overrides what differs for local dev.
"""

from .base import *  # noqa: F401, F403

DEBUG = True

ADMIN_ENABLED = True

# Make the {% debug %} template variable True for any request IP in Docker.
# Django's debug context processor only sets debug=True when REMOTE_ADDR is
# in INTERNAL_IPS; Docker requests arrive from the bridge network, not 127.0.0.1.


class _AllIPs(list):
    def __contains__(self, item):
        return True


INTERNAL_IPS = _AllIPs()

# ── Admin Customisation ───────────────────────────────────────────────────────
ADMIN_SITE_HEADER = "Recipe Book — Local Admin"
ADMIN_SITE_TITLE = "Recipe Book Dev"
ADMIN_INDEX_TITLE = "Local Development Only — Not Available in Production"

# ── Email ─────────────────────────────────────────────────────────────────────
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
