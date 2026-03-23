import json
import re
import datetime
import psycopg2
from fastmcp import FastMCP
from openai import OpenAI
from starlette.responses import JSONResponse
from prometheus_client import Counter, Histogram, Gauge, start_http_server
from policy_engine import PolicyEngine
from shared.logger import get_logger
from shared.middleware import TRACE_ID_VAR
import time
import uuid


policy = PolicyEngine()
logger = get_logger("triage_agent")

# -----------------------------
# CONSTANTS for COST
# -----------------------------
# GPT-4o pricing per 1 token (Approximate)
COST_PER_INPUT_TOKEN = 0.000005  # $5.00 per 1M tokens
COST_PER_OUTPUT_TOKEN = 0.000015 # $15.00 per 1M tokens

# -----------------------------
# PROMETHEUS METRICS
# -----------------------------
CLASSIFICATION_LATENCY = Histogram('triage_classification_seconds', 'Total time taken for classifying the incidents')
SEVERITY_COUNTER = Counter('triage_severity_total', 'Count of incidents by Severity', ['severity'])
HTTP_REQUESTS_TOTAL = Counter('http_requests_total', 'Total number of HTTP requests received')
HTTP_REQUEST_DURATION = Histogram('http_request_duration_seconds', 'Duration of HTTP requests in seconds')
LLM_CALL_COUNT = Counter('llm_call_count', 'Number of LLM calls made')
LLM_CALL_DURATION = Histogram('llm_call_duration_seconds', 'Duration of LLM calls in seconds')
LLM_TOKEN_USAGE_TOTAL = Counter('llm_token_usage_total', 'Total tokens used by LLM', ['token_type'])
LLM_COST_TOTAL = Counter('llm_cost_total', 'Total cost of LLM calls in USD')
LLM_ERROR_COUNT = Counter('llm_error_count', 'Number of LLM errors')
LLM_RETRY_COUNT = Counter('llm_retry_count', 'Number of LLM retries')
DB_CONNECTION_COUNT = Counter('db_connection_count', 'Number of DB connections opened')
SEVERITY_ENTROPY = Gauge('severity_entropy', 'Entropy of severity distribution')
CLASSIFICATION_CONFIDENCE = Gauge('classification_confidence', 'AI model classification confidence score (0-1)', ['severity'])

def update_severity_entropy():
    from math import log
    counts = {
        "LOW": SEVERITY_COUNTER.labels(severity="LOW")._value.get(),
        "MEDIUM": SEVERITY_COUNTER.labels(severity="MEDIUM")._value.get(),
        "HIGH": SEVERITY_COUNTER.labels(severity="HIGH")._value.get(),
        "CRITICAL": SEVERITY_COUNTER.labels(severity="CRITICAL")._value.get(),
    }
    total = sum(counts.values())
    if total == 0:
        return
    entropy = 0.0
    for count in counts.values():
        if count > 0:
            p = count / total
            entropy -= p * log(p)
    SEVERITY_ENTROPY.set(entropy)

# -----------------------------
# SECRETS & REGISTRY
# -----------------------------
def read_secret(path):
    with open(path, "r") as f:
        return f.read().strip()

SECRET_PATH = "/etc/secret"
secrets = {
    "DB_HOST": read_secret(f"{SECRET_PATH}/DB_HOST"),
    "DB_NAME": read_secret(f"{SECRET_PATH}/DB_NAME"),
    "DB_USER": read_secret(f"{SECRET_PATH}/DB_USER"),
    "DB_PASSWORD": read_secret(f"{SECRET_PATH}/DB_PASSWORD"),
    "OPENAI_API_KEY": read_secret(f"{SECRET_PATH}/OPENAI_API_KEY")
}

mcp = FastMCP("Triage Agent")

class PromptRegistry:
    def __init__(self):
        self._prompt_registry = {
            "v1.0.0": (
                "You are a 311 incident classifier. Classify this complaint:\n"
                "Description: {description}\n"
                "Classify as: LOW, MEDIUM, HIGH, or CRITICAL\n"
                "Return ONLY JSON: {{\"severity\": \"...\", \"confidence\": 0.0-1.0}}"
            ),
            "v1.1.0": (
                "You are a 311 incident classifier. Classify this complaint:\n"
                "Description: {description}\n"
                "Classify as: LOW, MEDIUM, HIGH, or CRITICAL\n"
                "Return ONLY JSON: {{\"severity\": \"...\", \"confidence\": 0.0-1.0, "
                "\"reasoning\": \"(Short explanation)\"}}"
            )
        }
        self._current_version = "v1.1.0"

    def get_prompt(self):
        return self._prompt_registry[self._current_version], self._current_version

current_prompt = PromptRegistry()
# Initialize client globally to reuse connection pool
client = OpenAI(api_key=secrets["OPENAI_API_KEY"])

# -----------------------------
# HEALTH CHECKS
# -----------------------------

@mcp.custom_route("/health", methods=["GET"])
async def health(request):
    return JSONResponse({"status": "ok"})

@mcp.custom_route("/ready", methods=["GET"])
async def ready_check(request):
    try:
        conn = psycopg2.connect(
            host=secrets["DB_HOST"],
            database=secrets["DB_NAME"],
            user=secrets["DB_USER"],
            password=secrets["DB_PASSWORD"],
            connect_timeout=3
        )
        conn.close()
        return JSONResponse({"status": "ready"})
    except Exception:
        return JSONResponse({"status": "not ready"}, status_code=503)

# -----------------------------
# MAIN TRIAGE ENDPOINT
# -----------------------------
@mcp.tool()
async def classify_incident(description: str, incident_id: str,
                            address: str | None = None,
                            image_url: str | None = None) -> str:
    trace_id= str(uuid.uuid4())
    TRACE_ID_VAR.set(trace_id)
    logger.info('Received incident for classification', extra={"incident_id": incident_id})
    start_time = time.time()
    HTTP_REQUESTS_TOTAL.inc()

    with HTTP_REQUEST_DURATION.time():
        def redact_pii(text: str) -> str:
            text = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '[REDACTED_EMAIL]', text)
            text = re.sub(r'\b\d{10}\b|\b\d{3}[-.]?\d{3}[-.]?\d{4}\b|\b\d{3}[-.]?\d{4}\b', '[REDACTED_PHONE]', text)
            return text

        description = redact_pii(description)

        with CLASSIFICATION_LATENCY.time():
            prompt_template, prompt_version = current_prompt.get_prompt()
            
            LLM_CALL_COUNT.inc()

            try:
                logger.info('Sending request to LLM', extra={"incident_id": incident_id})
                with LLM_CALL_DURATION.time():
                    response = client.chat.completions.create(
                        model='gpt-4o',
                        messages=[{'role': 'user', 'content': prompt_template.format(description=description)}],
                        response_format={"type": "json_object"},
                        temperature=0.1
                    )
            except Exception as e:
                logger.error('LLM call failed', 
                             extra={"incident_id": incident_id, "error_type": type(e).__name__, "error_message": str(e)}, 
                             exc_info=True)
                LLM_ERROR_COUNT.inc()
                raise e

            response_content = response.choices[0].message.content

            # -----------------------------
            # TOKEN + COST CALCULATION
            # -----------------------------
            usage = response.usage
            prompt_tokens = usage.prompt_tokens
            completion_tokens = usage.completion_tokens
            
            # Update detailed token counters
            LLM_TOKEN_USAGE_TOTAL.labels(token_type="input").inc(prompt_tokens)
            LLM_TOKEN_USAGE_TOTAL.labels(token_type="output").inc(completion_tokens)

            # Calculate and update cost
            total_cost = (prompt_tokens * COST_PER_INPUT_TOKEN) + (completion_tokens * COST_PER_OUTPUT_TOKEN)
            LLM_COST_TOTAL.inc(total_cost)

            # -----------------------------
            # PARSE & PERSIST
            # -----------------------------
            try:
                logger.info('Parsing LLM response', extra={"incident_id": incident_id})
                data = json.loads(response_content)
                ai_severity_value = data.get("severity", "UNKNOWN")
                confidence_value = data.get("confidence", 0.0)
                reasoning_value = data.get("reasoning", "No explanation provided")

                CLASSIFICATION_CONFIDENCE.labels(severity=ai_severity_value).set(confidence_value)
                zip_code_match = re.search(r'(\d{5})$', address) if address else None
                zip_code = zip_code_match.group(1) if zip_code_match else None
                address_string = address.split(',')[0].strip() if address else ""

                SEVERITY_COUNTER.labels(severity=ai_severity_value).inc()
                update_severity_entropy()
							   
                print('description:',description)
                print('ai_severity_value:',ai_severity_value)
                print('confidence_value:', confidence_value)
                print('image_url:',image_url)

                needs_review=False
                if ai_severity_value in ["CRITICAL", "HIGH"] or confidence_value <= 0.8:
                    needs_review = True
                    logger.info('Incident requires review', extra={"incident_id": incident_id, "confidence": confidence_value})
									
                # -----------------------------
                # POLICY ENGINE
                # -----------------------------
                governed_result = policy.enforce_policies(
                    description=description,
                    ai_result={
                        "severity": ai_severity_value,
                        "confidence": confidence_value,
                        "reasoning": reasoning_value
                    }
                )
														  
                print('governed_result:', governed_result)																		  
																				 
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                initial_log = f"[{timestamp}] Initial Severity classified as {ai_severity_value} by AI Agent (confidence: {confidence_value:.2f})"																							 
												  
                severity_value = ai_severity_value
                if ai_severity_value!=governed_result['severity']:
                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    new_log = f"[{timestamp}] Policy Override to {governed_result['severity']} (Note: {','.join(governed_result['applied_policies'])})\n"
                    initial_log = initial_log + new_log
                    severity_value=governed_result['severity']
                
                logger.info('Final severity after policy enforcement', 
                           extra={
                               "incident_id": incident_id, 
                               "final_severity": severity_value,
                               "ai_severity": ai_severity_value,
                               "confidence": confidence_value
                           })
																					 
                # -----------------------------
                # DB INSERT
                # -----------------------------
                DB_CONNECTION_COUNT.inc()

                logger.info('Inserting incident into DB', extra={"incident_id": incident_id})
                with psycopg2.connect(
                    host=secrets["DB_HOST"],
                    database="incident_report",
                    user="db_admin",
                    password=secrets["DB_PASSWORD"]
                ) as conn:
                    with conn.cursor() as cur:
                        query = """
                        INSERT INTO incidents (
                            incident_id, description, ai_severity, severity,
                            confidence, image_url, needs_review, ai_reasoning,
                            prompt_version, deadline, policies_applied, address,
                            zip_code, data_source, transformation_log
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'SF_311_API', %s)
                        ON CONFLICT (incident_id) DO UPDATE SET
                            description = EXCLUDED.description,
                            ai_severity = EXCLUDED.ai_severity,
                            severity = EXCLUDED.severity,
                            confidence = EXCLUDED.confidence,
                            image_url = EXCLUDED.image_url,
                            needs_review = EXCLUDED.needs_review,
                            ai_reasoning = EXCLUDED.ai_reasoning,
                            prompt_version = EXCLUDED.prompt_version,
                            deadline = EXCLUDED.deadline,
                            policies_applied = EXCLUDED.policies_applied,
                            address = EXCLUDED.address,
                            zip_code = EXCLUDED.zip_code,
                            transformation_log = EXCLUDED.transformation_log
                        """
                        cur.execute(query, (
                            incident_id, description, ai_severity_value,
                            severity_value, confidence_value, image_url,
                            governed_result['needs_review'], reasoning_value,
                            prompt_version, governed_result['deadline'],
                            ','.join(governed_result['applied_policies']),
                            address_string, zip_code, initial_log
                        ))
                        conn.commit()
                
                duration_ms = int((time.time() - start_time) * 1000)
                logger.info('Classification complete', 
                            extra={
                                "incident_id": incident_id,
                                "duration_ms": duration_ms,
                                "final_severity": severity_value,
                                "confidence": confidence_value
                            })
                            
            except json.JSONDecodeError as e:
                logger.error('Failed to parse LLM response as JSON', 
                            extra={
                                "incident_id": incident_id, 
                                "response_content": response_content,
                                "error_type": type(e).__name__,
                                "error_message": str(e)
                            },
                            exc_info=True)
                raise

        return response_content

# -----------------------------
# MAIN ENTRYPOINT
# -----------------------------

if __name__ == "__main__":
    logger.info("Starting Triage Agent server", extra={"port": 8000, "metrics_port": 9090})
    start_http_server(9090)
    mcp.run(transport='sse', host="0.0.0.0", port=8000)
