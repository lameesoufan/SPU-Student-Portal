try:
    from .celery import app as celery_app
    __all__ = ('celery_app',)
except ImportError:
    # Celery not installed - recurring tasks will not run automatically
    # But the server will still work fine
    pass