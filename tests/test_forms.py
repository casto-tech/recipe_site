"""
Input validation tests — SearchForm and image upload validation.
All user input is validated through Django forms before reaching views or managers.
"""

import io

import pytest

from recipes.forms import RecipeImageForm, SearchForm


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
    def _make_jpeg(self, size_bytes=None):
        """Build a minimal valid JPEG byte stream."""
        jpeg_header = (
            b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
        )
        if size_bytes:
            padding = b'\x00' * (size_bytes - len(jpeg_header))
            return jpeg_header + padding
        return jpeg_header + b'\xff\xd9'

    def _upload_file(self, data, name):
        from django.core.files.uploadedfile import InMemoryUploadedFile
        f = io.BytesIO(data)
        return InMemoryUploadedFile(
            file=f,
            field_name='image',
            name=name,
            content_type='image/jpeg',
            size=len(data),
            charset=None,
        )

    def test_valid_jpeg_accepted(self):
        from recipes.utils import validate_image_upload
        jpeg_data = self._make_jpeg()
        f = self._upload_file(jpeg_data, 'photo.jpg')
        errors = validate_image_upload(f)
        assert errors == []

    def test_invalid_extension_rejected(self):
        from recipes.utils import validate_image_upload
        f = self._upload_file(b'not a real file', 'malware.exe')
        errors = validate_image_upload(f)
        assert len(errors) > 0
        assert any('.exe' in e for e in errors)

    def test_oversized_file_rejected(self):
        from recipes.utils import validate_image_upload
        # 6 MB file — exceeds 5 MB limit
        big_data = self._make_jpeg(6 * 1024 * 1024)
        f = self._upload_file(big_data, 'big.jpg')
        errors = validate_image_upload(f)
        assert any('5 MB' in e for e in errors)

    def test_file_at_exactly_5mb_boundary(self):
        from recipes.utils import validate_image_upload
        # Exactly 5 MB should pass
        exact_data = self._make_jpeg(5 * 1024 * 1024)
        f = self._upload_file(exact_data, 'exact.jpg')
        errors = validate_image_upload(f)
        # Only check that size error is not present (mime mismatch may occur for padding)
        assert not any('5 MB' in e for e in errors)

    def test_mime_type_mismatch_rejected(self):
        from recipes.utils import validate_image_upload
        # PNG magic bytes but .jpg extension
        png_header = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR'
        f = self._upload_file(png_header, 'fake.jpg')
        errors = validate_image_upload(f)
        assert len(errors) > 0

    def test_png_with_correct_extension_accepted(self):
        from recipes.utils import validate_image_upload
        png_header = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR' + b'\x00' * 100
        f = self._upload_file(png_header, 'image.png')
        errors = validate_image_upload(f)
        assert errors == []

    def test_webp_with_correct_extension_accepted(self):
        from recipes.utils import validate_image_upload
        # Minimal valid WebP magic bytes
        webp_data = b'RIFF\x24\x00\x00\x00WEBPVP8 '
        f = self._upload_file(webp_data, 'image.webp')
        errors = validate_image_upload(f)
        assert errors == []

    def test_non_image_content_with_webp_extension_rejected(self):
        from recipes.utils import validate_image_upload
        f = self._upload_file(b'this is not an image', 'fake.webp')
        errors = validate_image_upload(f)
        assert len(errors) > 0
