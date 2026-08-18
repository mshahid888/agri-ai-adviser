FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app/ ./app/
COPY knowledge/ ./knowledge/
COPY data/ ./data/

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser
USER appuser

# Expose port
EXPOSE ${API_PORT:-8000}

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${API_PORT:-8000}/api/v1/health')"

# Run
CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]
