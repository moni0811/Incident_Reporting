FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /incident_report

RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
        "python-jose[cryptography]>=3.4.0" \
        fastmcp \
        mcp \
        prometheus-client \
        requests \
        fastapi \
        uvicorn

COPY shared/ /incident_report/shared/
COPY escalation_agent/ /incident_report/

ENV PYTHONPATH=/incident_report

CMD ["python", "server.py"]
