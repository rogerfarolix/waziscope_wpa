FROM python:3.11-slim

WORKDIR /app

# Dépendances système pour yt-dlp (ffmpeg)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8032

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8032"]