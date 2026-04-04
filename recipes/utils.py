"""
Shared utility functions for the recipes app.
Any function used in more than one place lives here.
"""

import imghdr
import logging

logger = logging.getLogger('recipes')

ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB

# Map file extension to expected imghdr type
EXTENSION_TO_IMGHDR = {
    '.jpg': 'jpeg',
    '.jpeg': 'jpeg',
    '.png': 'png',
    '.webp': None,  # imghdr doesn't reliably detect webp — handled separately
}


def validate_image_upload(file):
    """Validate an uploaded image file.

    Checks:
    - File extension is in the allowed list
    - File size does not exceed MAX_IMAGE_SIZE_BYTES (5 MB)
    - MIME type matches the declared extension (prevents extension spoofing)

    Args:
        file: An InMemoryUploadedFile or TemporaryUploadedFile from Django.

    Returns:
        list[str]: A list of validation error messages (empty means valid).
    """
    errors = []

    # Extension check
    name = file.name.lower()
    ext = ''
    dot_idx = name.rfind('.')
    if dot_idx != -1:
        ext = name[dot_idx:]

    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        errors.append(
            f"Unsupported file type '{ext}'. "
            f"Allowed types: {', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))}"
        )
        return errors  # No point checking MIME if extension is wrong

    # Size check
    file.seek(0, 2)  # Seek to end
    size = file.tell()
    file.seek(0)     # Rewind

    if size > MAX_IMAGE_SIZE_BYTES:
        errors.append(
            f"File size {size / (1024 * 1024):.1f} MB exceeds the 5 MB maximum."
        )

    # MIME type check — read enough bytes for imghdr detection
    file.seek(0)
    header = file.read(512)
    file.seek(0)

    detected = imghdr.what(None, h=header)

    expected = EXTENSION_TO_IMGHDR.get(ext)
    if expected is not None and detected != expected:
        errors.append(
            f"File content does not match extension '{ext}'. "
            f"Expected {expected}, detected {detected or 'unknown'}."
        )
    elif ext == '.webp':
        # imghdr doesn't support webp; check the magic bytes directly
        if not header.startswith(b'RIFF') or b'WEBP' not in header[:12]:
            errors.append(
                "File content does not match extension '.webp'. "
                "The file does not appear to be a valid WebP image."
            )

    return errors
