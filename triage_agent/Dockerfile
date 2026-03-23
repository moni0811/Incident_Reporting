FROM python:3.11-slim
WORKDIR /incident_report
RUN pip install fastmcp openai python-dotenv psycopg2-binary prometheus-client fastapi uvicorn
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
COPY triage_agent/ /incident_report/
COPY shared/ /incident_report/shared/
ENV PYTHONPATH=/incident_report
CMD ["python", "server.py"]
