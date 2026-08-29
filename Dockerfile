FROM python:3.11-slim

WORKDIR /app

# System deps for lxml (used by the insider-trading scraper)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libxml2-dev libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/

WORKDIR /app/backend

ENV PYTHONUNBUFFERED=1 \
    ENV=production \
    PORT=8000

EXPOSE 8000

# DATABASE_URL should point at a persistent volume or managed Postgres in
# production -- the sqlite default file (./stockscanner.db) does not survive
# a container redeploy on most hosting platforms.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
