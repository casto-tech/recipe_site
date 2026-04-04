"""
RecipeManager — all shared query logic lives here.
Views never rewrite query logic; they call manager methods only.
This is the DRY enforcement point for all database access patterns.
"""

from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db import models


class RecipeManager(models.Manager):
    def with_tags(self):
        """Base queryset used by all views — always prefetch tags."""
        return self.prefetch_related('tags')

    def search(self, query=None, tag_slug=None):
        """Single method for all search and filter operations.

        Args:
            query: Free-text search string (searches title and tag names).
            tag_slug: Exact tag slug to filter by.

        Returns:
            Queryset ordered by relevance rank (when query provided)
            or newest-first (no query).
        """
        qs = self.with_tags()

        if query:
            search_vector = (
                SearchVector('title', weight='A')
                + SearchVector('tags__name', weight='B')
            )
            search_query = SearchQuery(query)
            qs = (
                qs.annotate(rank=SearchRank(search_vector, search_query))
                .filter(rank__gte=0.1)
                .order_by('-rank')
            )
        else:
            qs = qs.order_by('-created_at')

        if tag_slug:
            qs = qs.filter(tags__slug=tag_slug)

        return qs.distinct()
