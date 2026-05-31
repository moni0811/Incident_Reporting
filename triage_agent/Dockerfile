FROM python:3.11-slim
WORKDIR /incident_report
RUN pip install fastmcp openai python-dotenv psycopg2-binary prometheus-client fastapi uvicorn
FROM debian:13.5

# 1. Update OS packages (Fixes the libncursesw6/perl-base issues)
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

# 2. Ensure pip is updated and dependencies are installed
RUN pip install --upgrade pip setuptools wheel

COPY triage_agent/ /incident_report/
COPY shared/ /incident_report/shared/
ENV PYTHONPATH=/incident_report
CMD ["python", "server.py"]
