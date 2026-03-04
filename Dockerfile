FROM python:3.11-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Tools needed for backups:
# - pg_dump (postgresql-client)
# - mongodump (mongodb-database-tools)
RUN apt-get update
RUN apt-get install -y --no-install-recommends wget curl gnupg software-properties-common apt-transport-https ca-certificates lsb-release
RUN apt-get install -y --no-install-recommends postgresql-client
RUN curl -fsSL https://www.mongodb.org/static/pgp/server-6.0.asc|gpg --dearmor -o /etc/apt/trusted.gpg.d/mongodb-6.gpg
RUN echo "deb http://repo.mongodb.org/apt/debian bookworm/mongodb-org/6.0 main" | tee /etc/apt/sources.list.d/mongodb-org-6.0.list
RUN apt-get update
RUN apt-get install -y --no-install-recommends mongodb-database-tools
RUN rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY backend /app/backend
COPY frontend /app/frontend

EXPOSE 8000

CMD ["python", "-m", "backend.app.main"]
