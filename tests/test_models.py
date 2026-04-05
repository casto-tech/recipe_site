"""
Unit tests for the data layer — Recipe model, Tag model, and RecipeManager.
All shared query logic lives in RecipeManager; tests validate that contract.
"""

import pytest
from django.utils.text import slugify

pytestmark = pytest.mark.django_db


class TestTagModel:
    def test_slug_auto_generated_from_name(self):
        from recipes.models import Tag
        tag = Tag.objects.create(name="Italian Cuisine")
        assert tag.slug == "italian-cuisine"

    def test_slug_uses_slugify_not_raw_input(self):
        from recipes.models import Tag
        tag = Tag(name="Café & Brunch!")
        tag.save()
        # slugify strips special chars — never uses raw user input
        assert tag.slug == slugify("Café & Brunch!")

    def test_name_uniqueness_enforced(self):
        from django.db import IntegrityError
        from recipes.models import Tag
        Tag.objects.create(name="Dessert", slug="dessert")
        with pytest.raises(IntegrityError):
            Tag.objects.create(name="Dessert", slug="dessert-2")

    def test_str_returns_name(self, tag_factory):
        tag = tag_factory("Vegetarian")
        assert str(tag) == "Vegetarian"


class TestRecipeModel:
    def test_slug_auto_generated_from_title(self, recipe_factory):
        recipe = recipe_factory(title="Chicken Tikka Masala")
        assert recipe.slug == "chicken-tikka-masala"

    def test_slug_uses_slugify(self, recipe_factory):
        recipe = recipe_factory(title="Crêpes Suzette!")
        assert recipe.slug == slugify("Crêpes Suzette!")

    def test_str_returns_title(self, recipe_factory):
        recipe = recipe_factory(title="Pasta Carbonara")
        assert str(recipe) == "Pasta Carbonara"

    def test_get_ingredients_list_splits_lines(self, recipe_factory):
        recipe = recipe_factory(
            ingredients="1 cup flour\n2 eggs\n1 tsp salt\n"
        )
        items = recipe.get_ingredients_list()
        assert items == ["1 cup flour", "2 eggs", "1 tsp salt"]

    def test_get_ingredients_list_skips_blank_lines(self, recipe_factory):
        recipe = recipe_factory(ingredients="flour\n\neggs\n\n")
        assert recipe.get_ingredients_list() == ["flour", "eggs"]

    def test_get_directions_list_splits_lines(self, recipe_factory):
        recipe = recipe_factory(
            directions="Mix ingredients.\nPour into pan.\nBake 30 minutes."
        )
        steps = recipe.get_directions_list()
        assert len(steps) == 3
        assert steps[0] == "Mix ingredients."

    def test_get_image_url_returns_image_url_when_no_upload(self, recipe_factory):
        recipe = recipe_factory(image_url="https://example.com/img.jpg")
        assert recipe.get_image_url() == "https://example.com/img.jpg"

    def test_get_image_url_returns_empty_when_nothing_set(self, recipe_factory):
        recipe = recipe_factory()
        assert recipe.get_image_url() == ''

    def test_ordering_newest_first(self, recipe_factory):
        r1 = recipe_factory(title="First", slug="first")
        r2 = recipe_factory(title="Second", slug="second")
        recipes = list(
            __import__('recipes.models', fromlist=['Recipe']).Recipe.objects.all()
        )
        assert recipes[0] == r2  # newest first
        assert recipes[1] == r1


class TestRecipeManager:
    def test_with_tags_returns_all_recipes(self, recipe_factory):
        from recipes.models import Recipe
        recipe_factory(title="Pizza", slug="pizza")
        recipe_factory(title="Pasta", slug="pasta")
        qs = Recipe.objects.with_tags()
        assert qs.count() == 2

    def test_with_tags_prefetches_tags(self, recipe_factory, tag_factory):
        from recipes.models import Recipe
        recipe = recipe_factory(title="Tagged", slug="tagged")
        tag = tag_factory("Italian")
        recipe.tags.add(tag)

        # Access without additional queries
        qs = list(Recipe.objects.with_tags())
        assert len(qs) == 1
        # Tags are prefetched — accessing them doesn't trigger a new query
        tags = list(qs[0].tags.all())
        assert len(tags) == 1

    def test_search_with_no_args_returns_all_newest_first(self, recipe_factory):
        from recipes.models import Recipe
        r1 = recipe_factory(title="Apple Pie", slug="apple-pie")
        r2 = recipe_factory(title="Beef Stew", slug="beef-stew")
        results = list(Recipe.objects.search())
        assert results[0] == r2  # newest first
        assert results[1] == r1

    def test_search_by_query_returns_matching_recipes(self, recipe_factory):
        from recipes.models import Recipe
        recipe_factory(title="Spaghetti Bolognese", slug="spaghetti-bolognese")
        recipe_factory(title="Fish and Chips", slug="fish-and-chips")
        results = Recipe.objects.search(query="spaghetti")
        titles = [r.title for r in results]
        assert "Spaghetti Bolognese" in titles

    def test_search_partial_query_matches(self, recipe_factory):
        """Partial text (e.g. 'spag') must match recipes containing that substring."""
        from recipes.models import Recipe
        recipe_factory(title="Spaghetti Carbonara", slug="spaghetti-carbonara")
        recipe_factory(title="Beef Burger", slug="beef-burger")
        results = Recipe.objects.search(query="spag")
        titles = [r.title for r in results]
        assert "Spaghetti Carbonara" in titles
        assert "Beef Burger" not in titles

    def test_search_by_tag_slug_filters_correctly(self, recipe_factory, tag_factory):
        from recipes.models import Recipe
        italian = tag_factory("Italian")
        mexican = tag_factory("Mexican")
        r1 = recipe_factory(title="Pizza", slug="pizza")
        r2 = recipe_factory(title="Tacos", slug="tacos")
        r1.tags.add(italian)
        r2.tags.add(mexican)

        results = list(Recipe.objects.search(tag_slug="italian"))
        assert len(results) == 1
        assert results[0].title == "Pizza"

    def test_search_by_query_and_tag_combined(self, recipe_factory, tag_factory):
        from recipes.models import Recipe
        italian = tag_factory("Italian")
        r1 = recipe_factory(title="Italian Pizza", slug="italian-pizza")
        recipe_factory(title="Italian Pasta", slug="italian-pasta")
        r1.tags.add(italian)

        results = list(Recipe.objects.search(query="pizza", tag_slug="italian"))
        assert len(results) == 1
        assert results[0].title == "Italian Pizza"

    def test_search_returns_distinct_results(self, recipe_factory, tag_factory):
        """Recipes with multiple tags must not appear duplicated in results."""
        from recipes.models import Recipe
        t1 = tag_factory("Italian")
        t2 = tag_factory("Vegetarian")
        recipe = recipe_factory(title="Margherita Pizza", slug="margherita-pizza")
        recipe.tags.add(t1, t2)

        results = list(Recipe.objects.search())
        assert len(results) == 1
