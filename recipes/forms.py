"""
Forms for the recipes app.
All user-supplied input is validated here before reaching any view or manager logic.
"""

import re

from django import forms

from .utils import validate_image_upload


class SearchForm(forms.Form):
    """Validates search and tag filter parameters from the search endpoint."""

    q = forms.CharField(
        required=False,
        max_length=200,
        strip=True,
    )
    tag = forms.CharField(
        required=False,
        max_length=100,
        strip=True,
    )

    def clean_tag(self):
        """Validate tag slug — only lowercase alphanumeric and hyphens allowed."""
        tag = self.cleaned_data.get('tag', '')
        if tag and not re.fullmatch(r'[a-z0-9\-]+', tag):
            raise forms.ValidationError(
                "Tag filter must contain only lowercase letters, digits, and hyphens."
            )
        return tag


class RecipeImageForm(forms.Form):
    """Standalone image upload form used for upload validation in tests."""

    image = forms.ImageField(required=False)

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image:
            errors = validate_image_upload(image)
            if errors:
                raise forms.ValidationError(errors)
        return image
