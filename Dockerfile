FROM python:3.12-slim

# Keeps Python from buffering stdout/stderr — important for Docker log visibility
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install dependencies first (layer caches unless requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# /data is for persistent state — Garmin session token lives here.
# Map this to a persistent path on Unraid (e.g. /mnt/user/appdata/fitness-api/data).
VOLUME ["/data"]

EXPOSE 8000

# Run as non-root for basic security hygiene
RUN useradd -m -u 1000 appuser && chown -R appuser /app
USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
