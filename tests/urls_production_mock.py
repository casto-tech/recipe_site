"""
Minimal URL configuration that simulates production — no admin URL mounted.
Used by test_security.py to verify admin is absent under production settings.
"""

from django.urls import include, path

urlpatterns = [
    path("", include("recipes.urls")),
    # No admin URL — simulates production where ADMIN_ENABLED=False
]
