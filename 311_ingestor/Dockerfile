# Use the slim version for a smaller attack surface
FROM python:3.13-slim

# Set environment variables to keep the container clean
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system-level dependencies in one layer
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /incident_report

# Upgrade pip, then install dependencies
# We install these BEFORE copying the rest of the code to leverage Docker layer caching
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir requests boto3 psycopg2-binary

# Copy the rest of the application code
COPY . .

# Ensure the ingestor logic is ready to run
# Removed redundant WORKDIR/COPY/RUN commands
CMD ["python", "-u", "ingestor.py"]

