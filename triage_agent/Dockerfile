FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /incident_report

RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
        "python-jose[cryptography]>=3.4.0" \
        openai \
        python-dotenv \
        psycopg2-binary \
        prometheus-client \
        fastapi \
        uvicorn

COPY triage_agent/ /incident_report/
COPY shared/ /incident_report/shared/

ENV PYTHONPATH=/incident_report

CMD ["python", "server.py"]
