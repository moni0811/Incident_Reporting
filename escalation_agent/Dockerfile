FROM python:3.11-slim
WORKDIR /incident_report
RUN pip install fastmcp mcp asyncio prometheus-client requests fastapi
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
COPY ./shared/ /incident_report/shared/
COPY server.py /incident_report/server.py
ENV PYTHONPATH=/incident_report
CMD ["python", "server.py"]
