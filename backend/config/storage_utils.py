from urllib.parse import urlparse

from django.conf import settings


def media_url(file_field_url: str) -> str:
    if not file_field_url:
        return ""
    if getattr(settings, "USE_S3", False):
        return file_field_url
    return urlparse(file_field_url).path
