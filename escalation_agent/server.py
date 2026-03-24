import json
import os
from fastmcp import FastMCP
import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client 
from starlette.responses import JSONResponse
from prometheus_client import Counter, Histogram, start_http_server
import requests
from shared.logger import get_logger
from shared.middleware import TRACE_ID_VAR
import uuid

logger = get_logger("escalation_agent")

REQUESTS_TOTAL= Counter('escalation_requests_total', 'Total number of Escalation requests')
CLASSIFICATION_LATENCY= Histogram('decide_escalation_seconds', 'Total time taken for decide the classification')
SEVERITY_COUNTER= Counter('escalation_severity_total', 'Count of requests by Severity', ['severity'])

def read_secret(path):
    with open(path, "r") as f:
        return f.read().strip()
    
CONFIG_PATH = "/etc/config"

configs = {
    "TRIAGE_AGENT_URL": read_secret(f"{CONFIG_PATH}/TRIAGE_AGENT_URL"),
}

mcp = FastMCP("Escalation Agent")


@mcp.custom_route("/health", methods=["GET"])
async def health(request):
    return JSONResponse({"status": "ok"})

@mcp.custom_route("/ready", methods=["GET"])
async def ready(request):
    triage_url = configs["TRIAGE_AGENT_URL"]
    health_url = f"{triage_url}/health"

    try:
        response=requests.get(health_url, timeout=3)
        if response.status_code==200:
            return JSONResponse({"status":"ready", "triage_agent":"reacheable"})
        else:
            return JSONResponse({"status":"not ready", "reason":f"agent returned {response.status_code}"}, status_code=503)
    except Exception as e:
        return JSONResponse({"status":"not ready", "reason":" not reacheable", "error": str(e)}, status_code=503) 
    
@mcp.tool()
async def decide_escalation(description: str, incident_id: str, address: str | None = None, zip_code: str | None = None, image_url: str | None = None) -> str:
    """Decides the escalation based on incident severity"""
    try:
        trace_id = str(uuid.uuid4())
        TRACE_ID_VAR.set(trace_id)
        logger.info('Received incident for escalation decision', extra={"incident_id": incident_id})
        base_url = configs["TRIAGE_AGENT_URL"]
        url = f"{base_url}/sse"
        #url="http://triage-agent-service:80/sse"
        print(f"Using Triage Agent URL: {url}")
        REQUESTS_TOTAL.inc()

        with CLASSIFICATION_LATENCY.time():
            async with sse_client(url) as (read,write):
                async with ClientSession(read, write) as session:
                    await session.initialize()

                    result=await session.call_tool("classify_incident", arguments={"description":description, "incident_id":incident_id, "address": address, "image_url": image_url})
                    triage_result = result.content[0].text
                    final_data = json.loads(triage_result)
                    severity = final_data.get('severity', 'UNKNOWN')
                    needs_escalation = (severity in ['HIGH', 'CRITICAL'])
                    SEVERITY_COUNTER.labels(severity=severity).inc()
                    result = {
                    "incident_id": incident_id,
                    "triage_severity": severity,
                    "needs_escalation": needs_escalation,
                    "action": "Escalate immediately" if needs_escalation else "Back log"
                }
                return json.dumps(result)
    except Exception as e:
        logger.error("Error in decide_escalation", extra={"incident_id": incident_id, "error_type": type(e).__name__, "error_message": str(e)}, exc_info=True)
        raise

if __name__=='__main__':
    start_http_server(9090)
    mcp.run(transport="sse", host="0.0.0.0", port=8000)
