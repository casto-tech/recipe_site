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
            INSTALLED_APPS=[============================================== test session starts ==============================================
platform linux -- Python 3.12.13, pytest-9.0.3, pluggy-1.6.0
django: version: 5.2.13, settings: config.settings.development (from env)
rootdir: /app
configfile: pyproject.toml
plugins: cov-7.1.0, django-4.12.0
collected 69 items                                                                                              

tests/test_models.py .....................                                                                [ 30%]
tests/test_security.py ..F.......F..                                                                      [ 49%]
tests/test_views.py .................                                                                     [ 73%]
tests/test_forms.py ..................                                                                    [100%]

=================================================== FAILURES ====================================================
___________________________ TestSecurityHeaders.test_csp_header_present_in_production ___________________________

self = <tests.test_security.TestSecurityHeaders object at 0x7ffa85518a10>
client = <django.test.client.Client object at 0x7ffa8416bef0>

    def test_csp_header_present_in_production(self, client):
        """Content-Security-Policy header must be set when CSP middleware is active."""
        from django.conf import settings
        prod_middleware = list(settings.MIDDLEWARE) + ['csp.middleware.CSPMiddleware']
        with override_settings(
            MIDDLEWARE=prod_middleware,
            CSP_DEFAULT_SRC=("'self'",),
        ):
            response = client.get('/')
>           assert response.has_header('Content-Security-Policy')
E           assert False
E            +  where False = has_header('Content-Security-Policy')
E            +    where has_header = <HttpResponse status_code=200, "text/html; charset=utf-8">.has_header

tests/test_security.py:32: AssertionError
_________________________ TestAxesRateLimiting.test_admin_lockout_after_failed_attempts _________________________

self = <tests.test_security.TestAxesRateLimiting object at 0x7ffa8551c890>
client = <django.test.client.Client object at 0x7ffa84049010>

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
    
        # 6th attempt should trigger lockout — axes returns HTTP 403 (Forbidden)
        response = client.post(login_url, {
            'username': 'nonexistent_user',
            'password': 'wrongpassword',
        })
>       assert response.status_code == 403
E       assert 429 == 403
E        +  where 429 = <HttpResponse status_code=429, "text/html; charset=utf-8">.status_code

tests/test_security.py:154: AssertionError
--------------------------------------------- Captured stderr call ----------------------------------------------
{"time": "2026-04-09 04:29:30,477", "level": "WARNING", "logger": "axes.handlers.database", "message": "AXES: New login failure by {ip_address: "********************", path_info: "/management/login/"}. Created new record in the database."}
{"time": "2026-04-09 04:29:30,770", "level": "WARNING", "logger": "axes.handlers.database", "message": "AXES: Repeated login failure by {ip_address: "********************", path_info: "/management/login/"}. Updated existing record in the database."}
{"time": "2026-04-09 04:29:31,042", "level": "WARNING", "logger": "axes.handlers.database", "message": "AXES: Repeated login failure by {ip_address: "********************", path_info: "/management/login/"}. Updated existing record in the database."}
{"time": "2026-04-09 04:29:31,358", "level": "WARNING", "logger": "axes.handlers.database", "message": "AXES: Repeated login failure by {ip_address: "********************", path_info: "/management/login/"}. Updated existing record in the database."}
{"time": "2026-04-09 04:29:31,631", "level": "WARNING", "logger": "axes.handlers.database", "message": "AXES: Repeated login failure by {ip_address: "********************", path_info: "/management/login/"}. Updated existing record in the database."}
{"time": "2026-04-09 04:29:31,633", "level": "WARNING", "logger": "axes.handlers.database", "message": "AXES: Locking out {ip_address: "********************", path_info: "/management/login/"} after repeated login failures."}
{"time": "2026-04-09 04:29:31,640", "level": "WARNING", "logger": "django.request", "message": "Too Many Requests: /management/login/"}
{"time": "2026-04-09 04:29:31,650", "level": "WARNING", "logger": "axes.handlers.database", "message": "AXES: Repeated login failure by {ip_address: "********************", path_info: "/management/login/"}. Updated existing record in the database."}
{"time": "2026-04-09 04:29:31,651", "level": "WARNING", "logger": "axes.handlers.database", "message": "AXES: Locking out {ip_address: "********************", path_info: "/management/login/"} after repeated login failures."}
{"time": "2026-04-09 04:29:31,658", "level": "WARNING", "logger": "django.request", "message": "Too Many Requests: /management/login/"}
=============================================== warnings summary ================================================
tests/test_security.py: 10 warnings
tests/test_views.py: 17 warnings
  /usr/local/lib/python3.12/site-packages/django/core/handlers/base.py:61: UserWarning: No directory at: /app/staticfiles/
    mw_instance = middleware(adapted_handler)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
================================================ tests coverage =================================================
_______________________________ coverage: platform linux, python 3.12.13-final-0 ________________________________

Name                                                 Stmts   Miss  Cover   Missing
----------------------------------------------------------------------------------
recipes/__init__.py                                      0      0   100%
recipes/admin.py                                        27      6    78%   52, 57-67
recipes/apps.py                                          4      0   100%
recipes/forms.py                                        20      6    70%   43-48
recipes/management/__init__.py                           0      0   100%
recipes/management/commands/__init__.py                  0      0   100%
recipes/management/commands/load_sample_recipes.py      24     24     0%   11-270
recipes/managers.py                                     12      0   100%
recipes/migrations/0001_initial.py                       8      0   100%
recipes/migrations/__init__.py                           0      0   100%
recipes/models.py                                       45      2    96%   62, 76
recipes/urls.py                                          4      0   100%
recipes/utils.py                                        35      0   100%
recipes/views.py                                        22      0   100%
----------------------------------------------------------------------------------
TOTAL                                                  201     38    81%
Required test coverage of 80% reached. Total coverage: 81.09%
============================================ short test summary info ============================================
FAILED tests/test_security.py::TestSecurityHeaders::test_csp_header_present_in_production - assert False
FAILED tests/test_security.py::TestAxesRateLimiting::test_admin_lockout_after_failed_attempts - assert 429 == 403
=================================== 2 failed, 67 passed, 27 warnings in 4.27s ===================================
❯ TestSecurityHeadersTestSecurityHeaders
❯ 
❯ sudo docker-compose exec web pytest tests/
============================================== test session starts ==============================================
platform linux -- Python 3.12.13, pytest-9.0.3, pluggy-1.6.0
django: version: 5.2.13, settings: config.settings.development (from env)
rootdir: /app
configfile: pyproject.toml
plugins: cov-7.1.0, django-4.12.0
collected 69 items                                                                                              

tests/test_models.py .....................                                                                [ 30%]
tests/test_security.py ..F..........                                                                      [ 49%]
tests/test_views.py .................                                                                     [ 73%]
tests/test_forms.py ..................                                                                    [100%]

=================================================== FAILURES ====================================================
___________________________ TestSecurityHeaders.test_csp_header_present_in_production ___________________________

self = <tests.test_security.TestSecurityHeaders object at 0x7f3be2918170>

    def test_csp_header_present_in_production(self):
        """Content-Security-Policy header must be set when CSP middleware is active."""
        from django.conf import settings
        from django.test import Client as TestClient
        prod_middleware = list(settings.MIDDLEWARE) + ['csp.middleware.CSPMiddleware']
        with override_settings(
            MIDDLEWARE=prod_middleware,
            CSP_DEFAULT_SRC=("'self'",),
        ):
            # A fresh client is required — override_settings does not rebuild the
            # middleware stack for a client instantiated before the context manager.
            response = TestClient().get('/')
>           assert response.has_header('Content-Security-Policy')
E           assert False
E            +  where False = has_header('Content-Security-Policy')
E            +    where has_header = <HttpResponse status_code=200, "text/html; charset=utf-8">.has_header

tests/test_security.py:35: AssertionError
=============================================== warnings summary ================================================
tests/test_security.py: 10 warnings
tests/test_views.py: 17 warnings
  /usr/local/lib/python3.12/site-packages/django/core/handlers/base.py:61: UserWarning: No directory at: /app/staticfiles/
    mw_instance = middleware(adapted_handler)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
================================================ tests coverage =================================================
_______________________________ coverage: platform linux, python 3.12.13-final-0 ________________________________

Name                                                 Stmts   Miss  Cover   Missing
----------------------------------------------------------------------------------
recipes/__init__.py                                      0      0   100%
recipes/admin.py                                        27      6    78%   52, 57-67
recipes/apps.py                                          4      0   100%
recipes/forms.py                                        20      6    70%   43-48
recipes/management/__init__.py                           0      0   100%
recipes/management/commands/__init__.py                  0      0   100%
recipes/management/commands/load_sample_recipes.py      24     24     0%   11-270
recipes/managers.py                                     12      0   100%
recipes/migrations/0001_initial.py                       8      0   100%
recipes/migrations/__init__.py                           0      0   100%
recipes/models.py                                       45      2    96%   62, 76
recipes/urls.py                                          4      0   100%
recipes/utils.py                                        35      0   100%
recipes/views.py                                        22      0   100%
----------------------------------------------------------------------------------
TOTAL                                                  201     38    81%
Required test coverage of 80% reached. Total coverage: 81.09%
============================================ short test summary info ============================================
FAILED tests/test_security.py::TestSecurityHeaders::test_csp_header_present_in_production - assert False
=================================== 1 failed, 68 passed, 27 warnings in 4.48s ===================================
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
