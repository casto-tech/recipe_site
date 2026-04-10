"""
Unit tests for recipes/admin.py — tag_list and image_preview methods.
Methods are tested directly by instantiating RecipeAdmin, avoiding the need
to render full admin views.
"""

import pytest
from unittest.mock import MagicMock

pytestmark = pytest.mark.django_db


class TestRecipeAdminMethods:

    def _admin(self):
        from django.contrib.admin.sites import AdminSite
        from recipes.admin import RecipeAdmin
        from recipes.models import Recipe
        return RecipeAdmin(Recipe, AdminSite())

    # ── tag_list ──────────────────────────────────────────────────────────────

    def test_tag_list_with_tags_returns_comma_separated(self):
        t1, t2 = MagicMock(), MagicMock()
        t1.name, t2.name = "Italian", "Vegetarian"
        obj = MagicMock()
        obj.tags.all.return_value = [t1, t2]
        assert self._admin().tag_list(obj) == "Italian, Vegetarian"

    def test_tag_list_with_no_tags_returns_dash(self):
        obj = MagicMock()
        obj.tags.all.return_value = []
        assert self._admin().tag_list(obj) == "—"

    # ── image_preview ─────────────────────────────────────────────────────────

    def test_image_preview_with_uploaded_image(self):
        """obj.image is truthy — returns HTML with the image URL."""
        obj = MagicMock()
        obj.image.url = "/media/recipes/test.jpg"
        result = self._admin().image_preview(obj)
        assert "/media/recipes/test.jpg" in str(result)

    def test_image_preview_with_image_url_only(self):
        """No uploaded file, but image_url is set — returns HTML with image_url."""
        obj = MagicMock()
        obj.image = None
        obj.image_url = "https://example.com/img.jpg"
        result = self._admin().image_preview(obj)
        assert "https://example.com/img.jpg" in str(result)

    def test_image_preview_with_no_image(self):
        """Neither file nor URL — returns the placeholder string."""
        obj = MagicMock()
        obj.image = None
        obj.image_url = ""
        assert self._admin().image_preview(obj) == "(No image uploaded)"
