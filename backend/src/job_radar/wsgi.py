"""WSGI entry point for gunicorn: `gunicorn job_radar.wsgi:app`. The Flask
CLI loads it too (`flask --app job_radar.wsgi ...`)."""

from job_radar.app import EXTENSION, create_app
from job_radar.http import configure_throttle

app = create_app()
# Share the per-host rate limit with the worker through Redis, if configured.
configure_throttle(app.extensions[EXTENSION].config.redis_url)
