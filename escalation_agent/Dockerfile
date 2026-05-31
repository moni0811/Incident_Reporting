FROM python:3.13-slim

WORKDIR /incident_report

# Update OS packages to fix libncursesw6/perl-base CVEs
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

# Upgrade pip and install dependencies
# python-jose[cryptography] 3.4.0 fixes CVE-2024-33663 and drops ecdsa (fixes CVE-2024-23342)
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir python-jose[cryptography]==3.4.0 pyasn1==0.6.3 pyasn1-modules==0.4.1 cryptography==44.0.3 fastmcp mcp prometheus-client requests fastapi uvicorn

COPY shared/ /incident_report/shared/
COPY escalation_agent/ /incident_report/

ENV PYTHONPATH=/incident_report

CMD ["python", "server.py"]
