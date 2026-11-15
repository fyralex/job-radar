FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/src
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini ./
COPY migrations ./migrations
COPY src ./src

RUN useradd --create-home --uid 1000 app
USER app

EXPOSE 8000
# Apply migrations, then serve. The worker container runs `python -m job_radar.worker`.
CMD ["sh", "-c", "alembic upgrade head && exec gunicorn --bind 0.0.0.0:8000 --workers 2 --threads 4 --timeout 120 job_radar.wsgi:app"]
