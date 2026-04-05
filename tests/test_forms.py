"""
Input validation tests — SearchForm and image upload validation.
All user input is validated through Django forms before reaching views or managers.
"""

import io

import pytest
from PIL import Image

from recipes.forms import RecipeImageForm, SearchForm


def _make_image_bytes(fmt='JPEG', size=(10, 10)):
    """Generate a real, complete image using Pillow.

    Returns raw bytes of a valid image in the requested format.
    Pillow is already a project dependency so no extra installs needed.
    """
    buf = io.BytesIO()
    img = Image.new('RGB', size, color=(200, 150, 100))
    img.save(buf, format=fmt)
    return buf.getvalue()


def _upload_file(data, name, content_type='image/jpeg'):
    from django.core.files.uploadedfile import InMemoryUploadedFile
    f = io.BytesIO(data)
    return InMemoryUploadedFile(
        file=f,
        field_name='image',
        name=name,
        content_type=content_type,
        size=len(data),
        charset=None,
    )


class TestSearchForm:
    def test_valid_query_accepted(self):
        form = SearchForm(data={'q': 'chicken soup', 'tag': ''})
        assert form.is_valid()

    def test_empty_form_is_valid(self):
        """Search with no params is valid — returns all recipes."""
        form = SearchForm(data={'q': '', 'tag': ''})
        assert form.is_valid()

    def test_query_at_max_length_accepted(self):
        form = SearchForm(data={'q': 'a' * 200, 'tag': ''})
        assert form.is_valid()

    def test_query_exceeding_max_length_rejected(self):
        form = SearchForm(data={'q': 'a' * 201, 'tag': ''})
        assert not form.is_valid()
        assert 'q' in form.errors

    def test_valid_tag_slug_accepted(self):
        form = SearchForm(data={'q': '', 'tag': 'italian-food'})
        assert form.is_valid()

    def test_tag_with_special_chars_rejected(self):
        form = SearchForm(data={'q': '', 'tag': 'invalid tag!'})
        assert not form.is_valid()
        assert 'tag' in form.errors

    def test_tag_with_spaces_rejected(self):
        form = SearchForm(data={'q': '', 'tag': 'some tag'})
        assert not form.is_valid()

    def test_tag_with_uppercase_rejected(self):
        form = SearchForm(data={'q': '', 'tag': 'Italian'})
        assert not form.is_valid()

    def test_tag_alphanumeric_and_hyphen_accepted(self):
        form = SearchForm(data={'q': '', 'tag': 'quick-easy-30min'})
        assert form.is_valid()

    def test_query_is_stripped(self):
        form = SearchForm(data={'q': '  pizza  ', 'tag': ''})
        assert form.is_valid()
        assert form.cleaned_data['q'] == 'pizza'


class TestImageUploadValidation:
    def test_valid_jpeg_accepted(self):
        from recipes.utils import validate_image_upload
        f = _upload_file(_make_image_bytes('JPEG'), 'photo.jpg')
        errors = validate_image_upload(f)
        assert errors == []

    def test_valid_png_accepted(self):
        from recipes.utils import validate_image_upload
        f = _upload_file(_make_image_bytes('PNG'), 'photo.png', 'image/png')
        errors = validate_image_upload(f)
        assert errors == []

    def test_valid_webp_accepted(self):
        from recipes.utils import validate_image_upload
        f = _upload_file(_make_image_bytes('WEBP'), 'photo.webp', 'image/webp')
        errors = validate_image_upload(f)
        assert errors == []

    def test_invalid_extension_rejected(self):
        from recipes.utils import validate_image_upload
        f = _upload_file(b'not a real file', 'malware.exe')
        errors = validate_image_upload(f)
        assert len(errors) > 0
        assert any('.exe' in e for e in errors)

    def test_oversized_file_rejected(self):
        from recipes.utils import validate_image_upload
        # Build a real JPEG then pad it past 5 MB
        base = _make_image_bytes('JPEG')
        big_data = base + b'\x00' * (6 * 1024 * 1024)
        f = _upload_file(big_data, 'big.jpg')
        errors = validate_image_upload(f)
        assert any('5 MB' in e for e in errors)

    def test_file_at_exactly_5mb_boundary(self):
        from recipes.utils import validate_image_upload
        # Build a real image padded to exactly 5 MB — should not trigger size error.
        # The padding makes it unreadable by Pillow so we only assert no size error.
        base = _make_image_bytes('JPEG')
        padding = b'\x00' * (5 * 1024 * 1024 - len(base))
        exact_data = base + padding
        f = _upload_file(exact_data, 'exact.jpg')
        errors = validate_image_upload(f)
        assert not any('5 MB' in e for e in errors)

    def test_mime_type_mismatch_rejected(self):
        from recipes.utils import validate_image_upload
        # A real PNG file uploaded with a .jpg extension — Pillow detects PNG, extension says JPEG
        png_data = _make_image_bytes('PNG')
        f = _upload_file(png_data, 'fake.jpg', 'image/jpeg')
        errors = validate_image_upload(f)
        assert len(errors) > 0
        assert any('PNG' in e or 'JPEG' in e for e in errors)

    def test_non_image_content_rejected(self):
        from recipes.utils import validate_image_upload
        f = _upload_file(b'this is not an image at all', 'fake.webp')
        errors = validate_image_upload(f)
        assert len(errors) > 0
