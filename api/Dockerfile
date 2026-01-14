FROM python:3.13-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy application code (includes llm/ subdirectory)
COPY . .

# Expose port (Railway uses $PORT)
EXPOSE 8000

# Run the API - use $PORT if set (Railway), otherwise 8000 (local)
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
