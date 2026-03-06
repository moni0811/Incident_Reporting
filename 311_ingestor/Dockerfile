FROM python:3.11-slim

WORKDIR /incident_report

# Install requests library
RUN pip install requests boto3 psycopg2-binary

COPY ingestor.py .

# -u means "Unbuffered" so logs show up instantly in Docker
CMD ["python", "-u", "ingestor.py"]