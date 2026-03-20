from django.apps import apps
from django.test.runner import DiscoverRunner


class UnmanagedModelTestRunner(DiscoverRunner):
    """Force unmanaged models to be managed during test DB creation."""

    def setup_databases(self, **kwargs):
        for model in apps.get_models():
            if not model._meta.managed:
                model._meta.managed = True
        return super().setup_databases(**kwargs)
