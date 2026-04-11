"""
Tests for management commands in the recipes app.
"""

import pytest
from django.core.management import call_command

pytestmark = pytest.mark.django_db


class TestLoadSampleRecipes:

    def test_creates_recipes_and_tags(self):
        from recipes.models import Recipe, Tag

        call_command("load_sample_recipes", verbosity=0)
        assert Recipe.objects.count() > 0
        assert Tag.objects.count() > 0

    def test_is_idempotent(self):
        """Running the command twice must not create duplicate records."""
        from recipes.models import Recipe, Tag

        call_command("load_sample_recipes", verbosity=0)
        recipe_count = Recipe.objects.count()
        tag_count = Tag.objects.count()
        # Second run hits the get_or_create else branch for all recipes
        call_command("load_sample_recipes", verbosity=0)
        assert Recipe.objects.count() == recipe_count
        assert Tag.objects.count() == tag_count
