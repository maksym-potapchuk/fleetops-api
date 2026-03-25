from django.apps import apps
from django.db import connection
from django.test.runner import DiscoverRunner


class UnmanagedModelTestRunner(DiscoverRunner):
    """Force unmanaged models to create tables during test DB setup."""

    _unmanaged_models: list = []

    def setup_databases(self, **kwargs):
        for model in apps.get_models():
            if not model._meta.managed:
                self._unmanaged_models.append(model)
                model._meta.managed = True

        result = super().setup_databases(**kwargs)

        # Create tables for formerly-unmanaged models that migrations skipped
        with connection.schema_editor() as editor:
            for model in self._unmanaged_models:
                try:
                    editor.create_model(model)
                except Exception:
                    pass  # table may already exist if migration created it

        return result

    def teardown_databases(self, old_config, **kwargs):
        for model in self._unmanaged_models:
            model._meta.managed = False
        super().teardown_databases(old_config, **kwargs)
