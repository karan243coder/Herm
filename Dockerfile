# Production Container with FFmpeg & System Toolchain
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

# Install system binaries: ffmpeg, curl, git, libgl (allows full video/audio editing)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    curl \
    ca-certificates \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application modules
COPY bot.py .
COPY agent/ ./agent/
COPY tools/ ./tools/
COPY skills/ ./skills/
COPY memory/ ./memory/
COPY cron/ ./cron/
COPY providers/ ./providers/

EXPOSE 8080

RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

CMD ["python", "bot.py"]
