FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy files
COPY . /app

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Expose port (Cloud Run uses 8080 by default)
ENV PORT 8080
EXPOSE 8080

# Run with gunicorn in production
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8080", "app:app"]
