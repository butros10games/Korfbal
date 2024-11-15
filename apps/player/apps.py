from django.apps import AppConfig


class PlayerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.player"

    def ready(self):
        import apps.player.signals  # noqa
