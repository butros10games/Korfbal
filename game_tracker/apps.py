from django.apps import AppConfig


class GameTrackerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'game_tracker'
    
    def ready(self):
        import game_tracker.signals
