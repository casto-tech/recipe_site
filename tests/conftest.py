"""
pytest fixtures shared across all test modules.
"""

import io

import pytest
from django.test import Client, override_settings


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def tag_factory(db):
    """Factory for creating Tag instances."""
    from recipes.models import Tag

    def _factory(name, slug=None):
        from django.utils.text import slugify

        return Tag.objects.create(name=name, slug=slug or slugify(name))

    return _factory


@pytest.fixture
def recipe_factory(db):
    """Factory for creating Recipe instances."""
    from recipes.models import Recipe

    def _factory(
        title="Test Recipe", ingredients="1 cup flour\n2 eggs", directions="Mix together.\nBake.", slug=None, **kwargs
    ):
        from django.utils.text import slugify

        return Recipe.objects.create(
            title=title,
            slug=slug or slugify(title),
            ingredients=ingredients,
            directions=directions,
            **kwargs,
        )

    return _factory


@pytest.fixture
def sample_jpeg_file():
    """Return a minimal valid JPEG file-like object."""
    # Minimal JPEG magic bytes
    jpeg_data = (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
        b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
        b"\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\x1e"
        b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00"
        b"\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b"
        b"\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xfb\xd5P\xff\xd9"
    )
    f = io.BytesIO(jpeg_data)
    f.name = "test.jpg"
    f.seek(0)
    return f


@pytest.fixture
def large_file():
    """Return a file-like object exceeding the 5 MB limit."""
    data = b"\xff\xd8\xff" + b"\x00" * (6 * 1024 * 1024)
    f = io.BytesIO(data)
    f.name = "big.jpg"
    f.seek(0)
    return f


@pytest.fixture
def production_settings():
    """Override settings to simulate production environment."""
    return override_settings(
        DJANGO_SETTINGS_MODULE="config.settings.production",
        DEBUG=False,
        ADMIN_ENABLED=False,
        INSTALLED_APPS=[
            app
            for app in [
                "django.contrib.auth",
                "django.contrib.contenttypes",
                "django.contrib.sessions",
                "django.contrib.messages",
                "django.contrib.staticfiles",
                "django.contrib.postgres",
                "axes",
                "recipes",
            ]
        ],
        SECURE_SSL_REDIRECT=False,  # Disable redirect for test client
    )
