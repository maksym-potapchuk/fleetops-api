from urllib.parse import urlparse

from django.conf import settings


def media_url(file_field_url: str) -> str:
    if not file_field_url:
        return ""
    if getattr(settings, "USE_S3", False):
        return file_field_url
    path = urlparse(file_field_url).path
    media_prefix = settings.MEDIA_URL  # e.g. "/media/"
    if not path.startswith(media_prefix):
        path = media_prefix + path.lstrip("/")
    return path
