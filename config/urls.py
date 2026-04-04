"""URL configuration for recipe_site."""

from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

urlpatterns = [
    path('', include('recipes.urls')),
]

# Admin is mounted ONLY when ADMIN_ENABLED is True (local dev only).
# In production ADMIN_ENABLED is False, django.contrib.admin is removed from
# INSTALLED_APPS, and no admin URL is ever registered — all admin paths
# return HTTP 404.
if getattr(settings, 'ADMIN_ENABLED', False):
    from django.contrib import admin

    admin.site.site_header = getattr(settings, 'ADMIN_SITE_HEADER', 'Admin')
    admin.site.site_title = getattr(settings, 'ADMIN_SITE_TITLE', 'Admin')
    admin.site.index_title = getattr(settings, 'ADMIN_INDEX_TITLE', 'Administration')
    admin.autodiscover()
    urlpatterns += [path('management/', admin.site.urls)]

# Serve media files in local development only
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=getattr(settings, 'MEDIA_ROOT', ''))
