# Deterministic image for Railway (takes precedence over Nixpacks/Railpack).
# curl is required: the Yahoo provider fetches through the curl binary on
# purpose — its TLS fingerprint with a bare UA passes Yahoo's bot scoring
# where python TLS stacks get 429-banned.
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
