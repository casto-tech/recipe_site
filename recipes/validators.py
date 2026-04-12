"""
Custom field validators for the recipes app.
"""

import ipaddress
from urllib.parse import urlparse

from django.core.exceptions import ValidationError


def validate_no_private_url(value):
    """
    Reject URLs that point to private, loopback, or reserved IP addresses
    to prevent Server-Side Request Forgery (SSRF) attacks.

    Allows only http and https schemes. Rejects localhost, 127.x, 169.254.x
    (cloud metadata endpoints), and all RFC-1918 private ranges.
    """
    if not value:
        return

    parsed = urlparse(value)

    if parsed.scheme not in ("http", "https"):
        raise ValidationError("Only http and https URLs are permitted.")

    hostname = parsed.hostname or ""

    # Reject well-known internal hostnames explicitly
    if hostname.lower() in ("localhost", "localhost.localdomain"):
        raise ValidationError("Internal hostnames are not permitted.")

    # Attempt IP address parsing — reject private/reserved ranges
    try:
        ip = ipaddress.ip_address(hostname)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_reserved
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise ValidationError("Private, loopback, and reserved IP addresses are not permitted.")
    except ValueError:
        pass  # hostname is a domain name — not an IP, no further check needed
