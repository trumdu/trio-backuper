FROM python:3.11-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Tools needed for backups:
# - pg_dump (postgresql-client)
# - mongodump (mongodb-database-tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
      postgresql-client \
      mongodb-database-tools \
      ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY backend /app/backend
COPY frontend /app/frontend

EXPOSE 8000

CMD ["python", "-m", "backend.app.main"]
