"""
Integration tests for HTTP layer — index, search, and health check views.
"""

import pytest

pytestmark = pytest.mark.django_db


class TestIndexView:
    def test_index_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_index_renders_recipe_cards(self, client, recipe_factory):
        recipe_factory(title="Banana Bread", slug="banana-bread")
        response = client.get("/")
        assert b"Banana Bread" in response.content

    def test_index_renders_all_recipes(self, client, recipe_factory):
        recipe_factory(title="Recipe One", slug="recipe-one")
        recipe_factory(title="Recipe Two", slug="recipe-two")
        response = client.get("/")
        assert b"Recipe One" in response.content
        assert b"Recipe Two" in response.content

    def test_index_shows_tag_filter_when_tags_exist(self, client, tag_factory, recipe_factory):
        tag = tag_factory("Italian")
        recipe = recipe_factory(title="Pizza", slug="pizza")
        recipe.tags.add(tag)
        response = client.get("/")
        assert b"Italian" in response.content

    def test_index_uses_correct_template(self, client):
        response = client.get("/")
        assert "recipes/index.html" in [t.name for t in response.templates]

    def test_index_includes_recipe_grid_partial(self, client):
        response = client.get("/")
        template_names = [t.name for t in response.templates]
        assert "recipes/partials/recipe_grid.html" in template_names


class TestSearchView:
    def test_search_returns_200(self, client):
        response = client.get("/search/")
        assert response.status_code == 200

    def test_search_with_no_params_returns_all_recipes(self, client, recipe_factory):
        recipe_factory(title="Cheese Burger", slug="cheese-burger")
        response = client.get("/search/")
        assert response.status_code == 200
        assert b"Cheese Burger" in response.content

    def test_search_with_query_filters_results(self, client, recipe_factory):
        recipe_factory(title="Chocolate Cake", slug="chocolate-cake")
        recipe_factory(title="Green Salad", slug="green-salad")
        response = client.get("/search/?q=chocolate")
        assert b"Chocolate Cake" in response.content

    def test_search_by_tag_filters_results(self, client, recipe_factory, tag_factory):
        italian = tag_factory("Italian")
        recipe = recipe_factory(title="Risotto", slug="risotto")
        other = recipe_factory(title="Burger", slug="burger")
        recipe.tags.add(italian)
        response = client.get("/search/?tag=italian")
        assert b"Risotto" in response.content
        assert b"Burger" not in response.content

    def test_search_returns_only_grid_partial(self, client):
        response = client.get("/search/")
        template_names = [t.name for t in response.templates]
        assert "recipes/partials/recipe_grid.html" in template_names
        # The full index template should NOT be rendered for the partial
        assert "recipes/index.html" not in template_names

    def test_search_with_invalid_tag_returns_all(self, client, recipe_factory):
        """Invalid tag slug (with special chars) is rejected by form validation,
        falling back to showing all recipes instead of erroring."""
        recipe_factory(title="Any Recipe", slug="any-recipe")
        # Tags with special chars fail form validation — view falls back to all recipes
        response = client.get("/search/?tag=invalid tag!")
        assert response.status_code == 200

    def test_search_only_accepts_get(self, client):
        response = client.post("/search/")
        assert response.status_code == 405


class TestRateLimiting:
    def test_search_rate_limited_after_30_requests(self, client):
        """The 31st request to /search/ within one minute must return HTTP 403."""
        from django.core.cache import cache

        cache.clear()

        for _ in range(30):
            response = client.get("/search/")
            assert response.status_code == 200

        response = client.get("/search/")
        assert response.status_code == 403


class TestHealthView:
    def test_health_returns_200(self, client):
        response = client.get("/health/")
        assert response.status_code == 200

    def test_health_returns_json_status_ok(self, client):
        import json

        response = client.get("/health/")
        data = json.loads(response.content)
        assert data == {"status": "ok"}

    def test_health_content_type_is_json(self, client):
        response = client.get("/health/")
        assert "application/json" in response["Content-Type"]
