FROM python:3.12-slim

WORKDIR /app

# системные либы для pillow/openpyxl (на всякий) + tzdata уже в python:slim
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY public/ ./public/

# data/ и secrets/ монтируются как volumes из docker-compose
RUN mkdir -p /app/data /app/secrets

CMD ["python", "-m", "app.bot"]
