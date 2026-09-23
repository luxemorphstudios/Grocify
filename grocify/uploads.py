"""Product image uploads.

Files are stored in ``grocify/static/uploads/products`` under a random name, so
nothing a user types ever becomes a path. Every upload is checked twice: the
extension must be an image extension, and the first bytes of the file must
actually look like that kind of image.
"""
import os
import uuid

from flask import current_app

MAX_IMAGE_BYTES = 2 * 1024 * 1024          # 2 MB per picture
ALLOWED = {"png", "jpg", "jpeg", "gif", "webp"}

# First bytes that every real file of this type starts with.
SIGNATURES = (
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"\xff\xd8\xff", "jpg"),
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
)


def _upload_dir():
    path = os.path.join(current_app.static_folder, "uploads", "products")
    os.makedirs(path, exist_ok=True)
    return path


def _sniff(head):
    """Return the real image type of these first bytes, or None."""
    for magic, kind in SIGNATURES:
        if head.startswith(magic):
            return kind
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    return None


def save_image(storage, old_name=None):
    """Store an uploaded picture. Returns ``(filename, error)``.

    ``(None, None)`` means no file was chosen, which is not an error.
    When a new file replaces ``old_name``, the old one is deleted.
    """
    if storage is None or not storage.filename:
        return None, None

    extension = storage.filename.rsplit(".", 1)[-1].lower() if "." in storage.filename else ""
    if extension not in ALLOWED:
        return None, "Please choose a PNG, JPG, GIF or WEBP image."

    storage.stream.seek(0, os.SEEK_END)
    size = storage.stream.tell()
    storage.stream.seek(0)
    if size == 0:
        return None, "That image file is empty."
    if size > MAX_IMAGE_BYTES:
        return None, "That image is %.1f MB. Please use one under 2 MB." % (size / 1048576)

    kind = _sniff(storage.stream.read(16))
    storage.stream.seek(0)
    if kind is None:
        return None, "That file is not a real image."

    filename = "%s.%s" % (uuid.uuid4().hex, kind)
    storage.save(os.path.join(_upload_dir(), filename))

    if old_name:
        delete_image(old_name)
    return filename, None


def delete_image(name):
    """Remove a stored picture; missing files are ignored."""
    if not name:
        return
    path = os.path.join(_upload_dir(), os.path.basename(name))
    try:
        os.remove(path)
    except OSError:
        pass
