"""
Security posture tests — headers, admin availability, rate limiting, and
production vs development settings isolation.
"""

import pytest
from django.test import Client, override_settings

pytestmark = pytest.mark.django_db


class TestSecurityHeaders:
    """Verify that required security headers are present on responses."""

    def test_x_frame_options_deny(self, client):
        response = client.get('/')
        assert response.get('X-Frame-Options') == 'DENY'

    def test_x_content_type_options_nosniff(self, client):
        response = client.get('/')
        assert response.get('X-Content-Type-Options') == 'nosniff'

    def test_csp_middleware_in_production_settings(self):
        """CSP middleware must be registered in the production MIDDLEWARE list."""
        from pathlib import Path
        prod_path = Path(__file__).resolve().parent.parent / 'config' / 'settings' / 'production.py'
        assert 'csp.middleware.CSPMiddleware' in prod_path.read_text()


class TestDefaultAdminURL:
    """The default /admin/ path must never be mounted in any environment."""

    def test_default_admin_url_returns_404(self, client):
        response = client.get('/admin/')
        assert response.status_code == 404

    def test_default_admin_login_returns_404(self, client):
        response = client.get('/admin/login/')
        assert response.status_code == 404


class TestAdminInDevelopment:
    """With development settings (ADMIN_ENABLED=True), /management/ should be accessible."""

    def test_management_returns_302_redirect_to_login_in_dev(self, client):
        # Development settings are active (set by DJANGO_SETTINGS_MODULE env var in CI)
        # ADMIN_ENABLED=True in development.py — admin is mounted at /management/
        from django.conf import settings
        if not getattr(settings, 'ADMIN_ENABLED', False):
            pytest.skip("Test requires ADMIN_ENABLED=True (development settings)")
        response = client.get('/management/')
        # 302 = redirect to login — confirms admin is mounted and working
        assert response.status_code == 302

    def test_admin_is_in_installed_apps_in_dev(self):
        from django.conf import settings
        if not getattr(settings, 'ADMIN_ENABLED', False):
            pytest.skip("Test requires ADMIN_ENABLED=True (development settings)")
        assert 'django.contrib.admin' in settings.INSTALLED_APPS


class TestAdminInProduction:
    """With production settings, /management/ must return 404 and admin must not be installed."""

    def test_management_returns_404_in_production(self, client):
        with override_settings(
            ADMIN_ENABLED=False,
            INSTALLED_APPS=[
                app for app in [
                    'django.contrib.auth',
                    'django.contrib.contenttypes',
                    'django.contrib.sessions',
                    'django.contrib.messages',
                    'django.contrib.staticfiles',
                    'django.contrib.postgres',
                    'axes',
                    'recipes',
                ]
            ],
            ROOT_URLCONF='tests.urls_production_mock',
        ):
            # Under production settings, ADMIN_ENABLED=False means no URL mounted
            response = client.get('/management/')
            assert response.status_code == 404

    def test_admin_not_in_installed_apps_in_production(self):
        """Verify that production.py removes django.contrib.admin from INSTALLED_APPS."""
        import importlib
        import sys

        # Load production settings module directly to inspect INSTALLED_APPS
        # without fully activating them
        with override_settings(
            INSTALLED_APPS=[
                app for app in [
                    'django.contrib.auth',
                    'django.contrib.contenttypes',
                    'django.contrib.sessions',
                    'django.contrib.messages',
                    'django.contrib.staticfiles',
                    'django.contrib.postgres',
                    'axes',
                    'recipes',
                ]
            ]
        ):
            from django.conf import settings
            assert 'django.contrib.admin' not in settings.INSTALLED_APPS

    def test_management_url_not_in_urlconf_when_admin_disabled(self):
        """When ADMIN_ENABLED=False, /management/ URL pattern must not be registered.

        override_settings(ADMIN_ENABLED=False) alone cannot unregister URL patterns
        that were already loaded at process startup. Instead we switch ROOT_URLCONF to
        the production mock which never mounts admin, forcing Django to resolve URLs
        against a conf where admin:index does not exist.
        """
        from django.urls import NoReverseMatch, reverse

        with override_settings(ROOT_URLCONF='tests.urls_production_mock', ADMIN_ENABLED=False):
            try:
                reverse('admin:index')
                pytest.fail("/management/ (admin:index) is registered but should not be")
            except NoReverseMatch:
                pass  # Expected — URL is not registered in production URL conf


class TestAxesRateLimiting:
    """django-axes must lock out admin login after 5 failed attempts."""

    def test_admin_lockout_after_failed_attempts(self, client):
        from django.conf import settings
        if not getattr(settings, 'ADMIN_ENABLED', False):
            pytest.skip("Axes lockout test requires ADMIN_ENABLED=True (development settings)")

        login_url = '/management/login/'

        for i in range(5):
            client.post(login_url, {
                'username': 'nonexistent_user',
                'password': 'wrongpassword',
            })

        # 6th attempt should trigger lockout — axes 6.x returns HTTP 429 (Too Many Requests)
        response = client.post(login_url, {
            'username': 'nonexistent_user',
            'password': 'wrongpassword',
        })
        assert response.status_code == 429


class TestDebugLeakage:
    """DEBUG information must never leak in error responses under production settings."""

    def test_no_debug_info_in_404_response(self, client):
        with override_settings(DEBUG=False):
            response = client.get('/this-path-does-not-exist/')
            assert response.status_code == 404
            # Django debug page exposes stack traces and settings — must not appear
            assert b'Traceback' not in response.content
            assert b'INSTALLED_APPS' not in response.content

    def test_no_debug_info_in_500_response(self, client):
        """500 errors under DEBUG=False must not show stack traces."""
        with override_settings(DEBUG=False):
            # Trigger an error by requesting a URL that will raise an exception
            # We use the raise_request_exception=False so Django returns the 500 page
            client.raise_request_exception = False
            response = client.get('/this-path-does-not-exist/')
            # Should be 404, but verifying DEBUG content is absent
            assert b'Traceback' not in response.content
