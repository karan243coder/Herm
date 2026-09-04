# Ultra-lightweight Python base image (~30MB RAM footprint)
FROM python:3.11-slim

# Prevent bytecode & buffer logs for real-time Koyeb console logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

# Install dependencies first (fast builds)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY bot.py .

# Expose port for Koyeb HTTP health checks
EXPOSE 8080

# Create non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Run bot
CMD ["python", "bot.py"]
