"""
Django admin configuration — local/development only.
This module is loaded only when ADMIN_ENABLED=True (development settings).
In production, django.contrib.admin is removed from INSTALLED_APPS entirely —
this file is never imported and admin is never accessible.
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import Recipe, Tag


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ('title', 'tag_list', 'created_at', 'updated_at')
    list_filter = ('tags',)
    search_fields = ('title', 'ingredients', 'directions')
    prepopulated_fields = {'slug': ('title',)}
    filter_horizontal = ('tags',)
    readonly_fields = ('image_preview', 'created_at', 'updated_at')

    fieldsets = (
        ('Recipe Details', {
            'fields': ('title', 'slug', 'tags'),
        }),
        ('Image', {
            'fields': ('image_preview', 'image', 'image_url'),
            'description': (
                'Upload an image for this recipe. '
                'The preview shows the currently saved image.'
            ),
        }),
        ('Content', {
            'fields': ('ingredients', 'directions'),
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def tag_list(self, obj):
        """Display comma-separated tag names in the list view."""
        return ', '.join(t.name for t in obj.tags.all()) or '—'
    tag_list.short_description = 'Tags'

    def image_preview(self, obj):
        """Render a thumbnail of the current image in the edit form."""
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height: 150px; border-radius: 6px;" />',
                obj.image.url,
            )
        if obj.image_url:
            return format_html(
                '<img src="{}" style="max-height: 150px; border-radius: 6px;" />',
                obj.image_url,
            )
        return '(No image uploaded)'
    image_preview.short_description = 'Current Image'
