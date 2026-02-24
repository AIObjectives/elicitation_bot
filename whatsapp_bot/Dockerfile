FROM python:3.12-slim

# ffmpeg is required by pydub for audio processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run injects PORT (default 8080); exec ensures uvicorn receives signals
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}
