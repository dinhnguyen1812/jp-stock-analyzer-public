FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies (optional: build tools, psycopg2)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# RUN pip install playwright
# RUN playwright install --with-deps

# Copy backend source code
COPY app ./app

