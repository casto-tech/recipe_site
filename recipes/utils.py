"""
Shared utility functions for the recipes app.
Any function used in more than one place lives here.
"""

import logging

from PIL import Image, UnidentifiedImageError

logger = logging.getLogger('recipes')

ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB

# Map extension to Pillow format string
EXTENSION_TO_PILLOW_FORMAT = {
    '.jpg': 'JPEG',
    '.jpeg': 'JPEG',
    '.png': 'PNG',
    '.webp': 'WEBP',
}


def validate_image_upload(file):
    """Validate an uploaded image file.

    Checks:
    - File extension is in the allowed list
    - File size does not exceed MAX_IMAGE_SIZE_BYTES (5 MB)
    - File content can be opened by Pillow and matches the declared extension

    Args:
        file: An InMemoryUploadedFile or TemporaryUploadedFile from Django.

    Returns:
        list[str]: A list of validation error messages (empty means valid).
    """
    errors = []

    # Extension check
    name = file.name.lower()
    dot_idx = name.rfind('.')
    ext = name[dot_idx:] if dot_idx != -1 else ''

    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        errors.append(
            f"Unsupported file type '{ext}'. "
            f"Allowed types: {', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))}"
        )
        return errors  # No point checking content if extension is wrong

    # Size check
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)

    if size > MAX_IMAGE_SIZE_BYTES:
        errors.append(
            f"File size {size / (1024 * 1024):.1f} MB exceeds the 5 MB maximum."
        )

    # MIME type check via Pillow — detects actual format from file content.
    # OSError covers truncated/corrupt files; UnidentifiedImageError covers
    # files Pillow cannot recognise as any known image format.
    file.seek(0)
    try:
        img = Image.open(file)
        img.verify()  # Fully validate the file structure
        file.seek(0)
        img = Image.open(file)  # Re-open after verify (verify closes the image)
        detected_format = img.format  # e.g. 'JPEG', 'PNG', 'WEBP'
    except (UnidentifiedImageError, OSError):
        errors.append(
            "File content does not appear to be a valid image."
        )
        file.seek(0)
        return errors
    finally:
        file.seek(0)

    expected_format = EXTENSION_TO_PILLOW_FORMAT.get(ext)
    if detected_format != expected_format:
        errors.append(
            f"File content does not match extension '{ext}'. "
            f"Expected {expected_format}, detected {detected_format or 'unknown'}."
        )

    return errors
