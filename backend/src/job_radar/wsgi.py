"""WSGI entry point for gunicorn: `gunicorn job_radar.wsgi:app`."""

from job_radar.app import create_app

app = create_app()
