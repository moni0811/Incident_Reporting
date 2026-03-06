FROM python:3.11-slim
WORKDIR /incident_report
RUN pip install fastmcp mcp asyncio prometheus-client requests
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
COPY server.py .
CMD ["python", "server.py"]