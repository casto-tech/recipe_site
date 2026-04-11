"""
RecipeManager — all shared query logic lives here.
Views never rewrite query logic; they call manager methods only.
This is the DRY enforcement point for all database access patterns.
"""

from django.db import models


class RecipeManager(models.Manager):
    def with_tags(self):
        """Base queryset used by all views — always prefetch tags."""
        return self.prefetch_related("tags")

    def search(self, query=None, tag_slug=None):
        """Single method for all search and filter operations.

        Uses icontains for partial/live search so typing a few characters
        immediately filters to matching recipes. Matches against title,
        tag names, and ingredients.

        Args:
            query: Free-text search string (partial match supported).
            tag_slug: Exact tag slug to filter by.

        Returns:
            Queryset ordered by newest-first.
        """
        qs = self.with_tags()

        if query:
            qs = qs.filter(
                models.Q(title__icontains=query)
                | models.Q(tags__name__icontains=query)
                | models.Q(ingredients__icontains=query)
            )

        qs = qs.order_by("-created_at")

        if tag_slug:
            qs = qs.filter(tags__slug=tag_slug)

        return qs.distinct()
