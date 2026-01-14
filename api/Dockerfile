FROM python:3.13-slim

WORKDIR /app

# Install dependencies
COPY api/pyproject.toml .
RUN pip install --no-cache-dir .

# Copy shared llm module
COPY llm/ ./llm/

# Copy application code
COPY api/ .

# Expose port
EXPOSE 8000

# Run the API
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
