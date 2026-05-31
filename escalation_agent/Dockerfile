FROM python:3.11-slim
WORKDIR /incident_report
RUN pip install fastmcp mcp asyncio prometheus-client requests fastapi

FROM debian:13.5

# 1. Update OS packages (Fixes the libncursesw6/perl-base issues)
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

# 2. Ensure pip is updated and dependencies are installed
RUN pip install --upgrade pip setuptools wheel

COPY shared/ /incident_report/shared/
COPY escalation_agent/ /incident_report/
ENV PYTHONPATH=/incident_report
CMD ["python", "server.py"]
