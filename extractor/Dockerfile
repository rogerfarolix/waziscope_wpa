FROM python:3.12-slim

WORKDIR /app

# Dépendances système pour yt-dlp (ffmpeg) + curl pour le healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Dépendances Python (couche cacheable)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# Code source
COPY . .

EXPOSE 8032

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8032/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8032"]