"""
Views for the recipes app.
All query logic is delegated to RecipeManager — never rewritten inline here.
"""

import logging

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET
from django_ratelimit.decorators import ratelimit

from .forms import SearchForm
from .models import Recipe, Tag

logger = logging.getLogger("recipes")


@require_GET
@ratelimit(key="ip", rate="60/m", block=True)
def index(request):
    """Main page — renders all recipe cards in newest-first order."""
    recipes = Recipe.objects.with_tags()
    tags = Tag.objects.all()
    return render(
        request,
        "recipes/index.html",
        {
            "recipes": recipes,
            "tags": tags,
        },
    )


@require_GET
@ratelimit(key="ip", rate="30/m", block=True)
def search(request):
    """HTMX search endpoint — returns the recipe_grid partial only.

    Accepts:
        ?q=   Free-text search (validated, max 200 chars)
        ?tag= Tag slug filter (validated, lowercase alphanumeric + hyphens only)

    Rate-limited to 30 requests per minute per IP.
    """
    form = SearchForm(request.GET)
    if form.is_valid():
        recipes = Recipe.objects.search(
            query=form.cleaned_data.get("q"),
            tag_slug=form.cleaned_data.get("tag"),
        )
    else:
        recipes = Recipe.objects.with_tags().order_by("-created_at")

    return render(request, "recipes/partials/recipe_grid.html", {"recipes": recipes})


def ratelimited(request, exception):
    logger.warning("Rate limit exceeded: %s", request.META.get("REMOTE_ADDR", "unknown"))
    response = HttpResponse("Too Many Requests", status=429, content_type="text/plain")
    response["Retry-After"] = "60"
    return response


@require_GET
@ratelimit(key="ip", rate="60/m", block=True)
def health(request):
    """Health check endpoint for Azure Container Apps probe.

    Returns HTTP 200 with {"status": "ok"}.
    No database query performed — this endpoint must be fast and always available.
    """
    return JsonResponse({"status": "ok"})
