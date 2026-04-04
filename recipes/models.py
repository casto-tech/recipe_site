"""
Recipe and Tag models.
All shared query logic is in RecipeManager — never inline in views.
"""

from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models
from django.utils.text import slugify

from .managers import RecipeManager


class Tag(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Recipe(models.Model):
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    image = models.ImageField(upload_to='recipes/', blank=True, null=True)
    image_url = models.URLField(
        blank=True,
        help_text="Developer-controlled fallback URL — never rendered from user input.",
    )
    tags = models.ManyToManyField(Tag, blank=True)
    ingredients = models.TextField(
        help_text="Enter one ingredient per line. Example: 2 cups flour"
    )
    directions = models.TextField(
        help_text="Enter one step per line. These will be displayed as a numbered list."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    search_vector = SearchVectorField(null=True, blank=True)

    objects = RecipeManager()

    class Meta:
        ordering = ['-created_at']
        indexes = [
            GinIndex(fields=['search_vector']),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def get_ingredients_list(self):
        """Return ingredients as a list, one item per line."""
        return [line.strip() for line in self.ingredients.splitlines() if line.strip()]

    def get_directions_list(self):
        """Return directions as a list, one step per line."""
        return [line.strip() for line in self.directions.splitlines() if line.strip()]

    def get_image_url(self):
        """Return the best available image URL for display."""
        if self.image:
            return self.image.url
        return self.image_url or ''
