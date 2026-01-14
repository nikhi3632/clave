FROM python:3.13-slim

WORKDIR /app

# Install psql for running migrations
RUN apt-get update && apt-get install -y postgresql-client && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY etl/pyproject.toml .
RUN pip install --no-cache-dir .

# Copy ETL code (includes llm_client.py)
COPY etl/ .
