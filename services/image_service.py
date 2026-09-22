"""Image support for fact fields.

Fact field values are plain strings, so an image is marked inline: a value that
starts with ``img:`` is an image reference rather than literal text.

    "portrait": "img:uploads/a3f9c1e8.png"       # uploaded, served from static/
    "portrait": "img:https://example.org/x.png"  # external URL

Keeping the marker inside the value means Domain.field_names stays a list of
plain strings, so a domain gains images without a schema change.
"""

import os
import uuid

from flask import current_app, url_for
from werkzeug.utils import secure_filename

IMAGE_MARKER = "img:"

# Directory under static/ where uploads are stored. Stored markers are
# relative to static/, so they double as the url_for('static') filename.
UPLOAD_SUBDIR = "uploads"

# SVG is deliberately excluded: it can carry script, and uploads are served
# from our own origin.
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

# .jpg and .jpeg are the same format; store one canonical extension.
CANONICAL_EXTENSIONS = {".jpg": ".jpeg"}

MAX_IMAGE_BYTES = 5 * 1024 * 1024

# Enough bytes to cover every signature checked below (WebP needs 12).
_HEADER_BYTES = 12


def canonical_extension(extension):
    """Collapse equivalent extensions to one spelling (.jpg -> .jpeg)."""
    return CANONICAL_EXTENSIONS.get(extension, extension)


def detect_image_type(header):
    """
    Identify an image format from its leading bytes.

    Extensions are attacker-controlled, so the file's actual content decides
    what it is.

    Args:
        header: First bytes of the file (at least _HEADER_BYTES)

    Returns:
        str: Canonical extension (e.g. ".png"), or None if unrecognised
    """
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if header.startswith(b"\xff\xd8\xff"):
        return ".jpeg"
    if header.startswith(b"GIF87a") or header.startswith(b"GIF89a"):
        return ".gif"
    if header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return ".webp"
    return None


def is_image_value(value):
    """
    Check whether a fact field value is an image reference.

    Args:
        value: A fact field value

    Returns:
        bool: True if the value carries the image marker
    """
    return isinstance(value, str) and value.startswith(IMAGE_MARKER)


def image_reference(value):
    """
    Strip the marker from an image value.

    Args:
        value: A fact field value

    Returns:
        str: The reference (path or URL), or None if not an image value
    """
    if not is_image_value(value):
        return None
    return value[len(IMAGE_MARKER) :]


def is_external_reference(reference):
    """
    Check whether a reference points at an external URL.

    Args:
        reference: An image reference (marker already stripped)

    Returns:
        bool: True for https:// URLs
    """
    return isinstance(reference, str) and reference.startswith("https://")


def image_src(value):
    """
    Resolve an image value to a URL the browser can load.

    Args:
        value: A fact field value

    Returns:
        str: URL for the image, or None if the value is not an image
    """
    reference = image_reference(value)
    if reference is None:
        return None
    if is_external_reference(reference):
        return reference
    return url_for("static", filename=reference)


def learn_card_alt(field_name, fact_data, identifying_field):
    """
    Build alt text for an image on the fact-display card.

    Descriptive text is safe here because the whole fact is on screen. Images
    shown during a quiz must NOT use this - naming the subject would give the
    answer away.

    Args:
        field_name: Field the image belongs to
        fact_data: The fact's data dict
        identifying_field: The domain's first field (usually "name")

    Returns:
        str: Alt text
    """
    label = field_name.replace("_", " ")
    subject = fact_data.get(identifying_field)

    if field_name != identifying_field and subject and not is_image_value(subject):
        return f"{label}: {subject}"
    return label


def _upload_folder():
    """Return the directory uploads are written to."""
    return current_app.config.get(
        "UPLOAD_FOLDER",
        os.path.join(current_app.static_folder, UPLOAD_SUBDIR),
    )


def save_uploaded_image(file):
    """
    Validate and store one uploaded image.

    Args:
        file: A werkzeug FileStorage

    Returns:
        str: Image value for a fact field (e.g. "img:uploads/a3f9c1e8.png")

    Raises:
        ValueError: If the file is not an allowed, recognisable image
    """
    filename = secure_filename(file.filename or "")
    if not filename:
        raise ValueError("An uploaded image has no usable filename")

    declared = canonical_extension(os.path.splitext(filename)[1].lower())
    allowed = {canonical_extension(ext) for ext in ALLOWED_EXTENSIONS}
    if declared not in allowed:
        raise ValueError(
            f"'{file.filename}' is not an allowed image type "
            f"({', '.join(sorted(ALLOWED_EXTENSIONS))})"
        )

    detected = detect_image_type(file.read(_HEADER_BYTES))
    if detected is None:
        raise ValueError(f"'{file.filename}' is not a recognised image file")
    if detected != declared:
        raise ValueError(
            f"'{file.filename}' has a {declared} extension but contains "
            f"{detected} data"
        )

    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size > MAX_IMAGE_BYTES:
        raise ValueError(
            f"'{file.filename}' is {size // 1024}KB; the limit is "
            f"{MAX_IMAGE_BYTES // 1024}KB"
        )

    # A random name keeps the original filename - which often names the answer
    # - out of the page source.
    stored_name = f"{uuid.uuid4().hex}{detected}"
    upload_folder = _upload_folder()
    os.makedirs(upload_folder, exist_ok=True)
    file.save(os.path.join(upload_folder, stored_name))

    return f"{IMAGE_MARKER}{UPLOAD_SUBDIR}/{stored_name}"


def save_uploaded_images(files):
    """
    Validate and store several uploaded images.

    Args:
        files: Iterable of werkzeug FileStorage objects (empty ones are skipped)

    Returns:
        dict: Original filename -> image value

    Raises:
        ValueError: If any file is rejected; files already stored are removed
    """
    saved = {}
    try:
        for file in files:
            if not file or not file.filename:
                continue
            saved[file.filename] = save_uploaded_image(file)
    except ValueError:
        discard_uploaded_images(saved.values())
        raise
    return saved


def discard_uploaded_images(values):
    """
    Delete stored uploads, e.g. when the domain they were for is rejected.

    Args:
        values: Iterable of image values returned by save_uploaded_image
    """
    prefix = f"{UPLOAD_SUBDIR}/"
    upload_folder = _upload_folder()

    for value in values:
        reference = image_reference(value)
        if reference is None or is_external_reference(reference):
            continue
        # Only ever delete files this module stored in the upload folder.
        if not reference.startswith(prefix) or ".." in reference:
            continue

        # Resolve against the folder we saved to, and by basename only, so a
        # reference can never point outside it.
        path = os.path.join(upload_folder, os.path.basename(reference))
        try:
            os.remove(path)
        except OSError:
            pass


def resolve_image_references(facts_data, uploaded_images):
    """
    Rewrite friendly image references in facts to stored image values.

    Teachers write ``img:erato.png`` in their JSON or CSV and upload
    ``erato.png`` alongside it; this swaps in the stored path. External
    ``https://`` references are kept as written. Anything else is rejected,
    which is also what stops a hand-written ``img:../../secret.png``.

    Args:
        facts_data: List of fact dicts
        uploaded_images: Original filename -> image value, from
            save_uploaded_images()

    Returns:
        list: New fact dicts with image references resolved

    Raises:
        ValueError: If a reference matches no upload and is not an https URL
    """
    by_name = {
        os.path.basename(name).lower(): value for name, value in uploaded_images.items()
    }

    resolved = []
    for fact in facts_data:
        new_fact = {}

        for field, value in fact.items():
            reference = image_reference(value)

            if reference is None or is_external_reference(reference):
                new_fact[field] = value
                continue

            if "://" in reference:
                raise ValueError(
                    f"Image reference '{reference}' for field '{field}' must "
                    f"use https://"
                )

            key = os.path.basename(reference).lower()
            if key not in by_name:
                raise ValueError(
                    f"No uploaded image named '{reference}' for field "
                    f"'{field}' - upload the file, or use an https:// URL"
                )

            new_fact[field] = by_name[key]

        resolved.append(new_fact)

    return resolved
