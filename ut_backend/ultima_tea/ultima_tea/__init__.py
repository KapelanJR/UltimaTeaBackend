from .celery import app as celery_app
from dotenv import load_dotenv

load_dotenv()
__all__ = ('celery_app',)
