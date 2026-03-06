import json
from pydoc import text
from symtable import Class
from fastmcp import FastMCP
from openai import OpenAI
import os
import psycopg2
from starlette.responses import JSONResponse
from prometheus_client import Counter, Histogram, start_http_server
import re
import datetime

from policy_engine import PolicyEngine
policy = PolicyEngine()

REQUESTS_TOTAL= Counter('triage_requests_total', 'Total number of Classification requests')
CLASSIFICATION_LATENCY= Histogram('triage_classification_seconds', 'Total time taken for classifying the incidents')
SEVERITY_COUNTER= Counter('triage_severity_total', 'Count of incidents by Severity', ['severity'])

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

mcp=FastMCP("Triage Agent")

class PromptRegistry:
    def __init__(self):
        self._prompt_registry = {
            "v1.0.0": "You are a 311 incident classifier. Classify this complaint:\nDescription: {description}\nClassify as: LOW, MEDIUM, HIGH, or CRITICAL\nReturn ONLY JSON: {{\"severity\": \"...\", \"confidence\": 0.0-1.0\"}}",
            "v1.1.0": "You are a 311 incident classifier. Classify this complaint:\nDescription: {description}\nClassify as: LOW, MEDIUM, HIGH, or CRITICAL\nReturn ONLY JSON: {{\"severity\": \"...\", \"confidence\": 0.0-1.0\", \"reasoning\": \"(Short explanation of why you chose this severity level)\"}}"
        }
        self._current_version = "v1.1.0"
    
    def get_prompt(self):
        return self._prompt_registry[self._current_version], self._current_version

current_prompt = PromptRegistry()

@mcp.custom_route("/health", methods=["GET"])
async def health(request):
    return JSONResponse({"status": "ok"})

@mcp.custom_route("/ready", methods=["GET"])
async def ready_check(request):
    #return JSONResponse({"status": "ready-dummy-test"})
    try:
        conn = psycopg2.connect(
            host=secrets["DB_HOST"],
            database=secrets["DB_NAME"],
            user=secrets["DB_USER"],
            password=secrets["DB_PASSWORD"],
            connect_timeout=3
        )
        conn.close()
        return JSONResponse({"status":"ready"})
    except Exception as e:
        return JSONResponse({"status":"not ready"}, status_code=503)

@mcp.tool()
async def classify_incident(description: str, incident_id: str, address: str | None = None,  image_url: str | None = None) -> str:
    """Classifies the severity based on description"""
    REQUESTS_TOTAL.inc()


    def redact_pii(text: str) -> str:
        text = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '[REDACTED_EMAIL]', text)
        text = re.sub(
            r'\b\d{10}\b'                    # 5550199123
            r'|\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'  # 555-555-1234
            r'|\b\d{3}[-.]?\d{4}\b',            # 555-0199  ← was missing
            '[REDACTED_PHONE]', text
        )
        return text
    description = redact_pii(description)
    
    with CLASSIFICATION_LATENCY.time():
        # prompt = f"""You are a 311 incident classifier. Classify this complaint:
        #         Description: {description}
        #         Classify as: LOW, MEDIUM, HIGH, or CRITICAL
        #         Return ONLY JSON: {{"severity": "...", "confidence": 0.0-1.0, "reasoning": "(Short explanation of why you chose this severity level)"}}"""
        # #return f"severity : CRITICAL, confidence : 0.9"
        prompt_template, prompt_version = current_prompt.get_prompt()

        client = OpenAI(api_key=secrets["OPENAI_API_KEY"])
        response = client.chat.completions.create(
                    model='gpt-4o',
                    messages=[{'role': 'user', 'content': prompt_template.format(description=description)}],
                    response_format={"type": "json_object"},
                    temperature= 0.1
                )
        #logging.info(response.choices[0].message.content)
        response_content = response.choices[0].message.content
        print(response_content)
        try:
            # 1. Convert string to a Python dictionary
            data = json.loads(response_content) 
            # 2. Extract values
            ai_severity_value = data.get("severity", "UNKNOWN")
            confidence_value = data.get("confidence", 0.0)
            reasoning_value = data.get("reasoning", "No explanation provided")
            
            zip_code_match = re.search(r'(\d{5})$', address) if address else None
            zip_code = zip_code_match.group(1) if zip_code_match else None
            address_string = address.split(',')[0].strip() if address else ""

            SEVERITY_COUNTER.labels(severity=ai_severity_value).inc()
            # 3. SQL INSERT
            #conn = psycopg2.connect(host=os.getenv("DB_HOST"), database="incident_report", user="db_admin", password=os.getenv('DB_PASSWORD'))
            #cur = conn.cursor()
            print('description:',description)
            print('ai_severity_value:',ai_severity_value)
            print('image_url:',image_url)
            #severity_value=ai_severity_value
            needs_review=False
            if ai_severity_value in ["CRITICAL", "HIGH"] or confidence_value <= 0.8:
                needs_review = True
                #severity_value=None
            
                print(f"High severity incident detected: {incident_id}")

            governed_result = policy.enforce_policies(
                description=description, 
                ai_result={
                    "severity": ai_severity_value,
                    "confidence": confidence_value,
                    "reasoning": reasoning_value
                }
            )
            print('governed_result:', governed_result)
            #response_content["applied_policies"]= governed_result["applied_policies"]
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            initial_log = f"[{timestamp}] Initial Severity classified as {ai_severity_value} by AI Agent"

            severity_value = ai_severity_value
            if ai_severity_value!=governed_result['severity']:
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                new_log = f"[{timestamp}] Policy Overide to {governed_result['severity']} (Note: {','.join(governed_result['applied_policies'])})\n"
                initial_log = initial_log + new_log
                severity_value=governed_result['severity']
            
            print("final severity_value:", severity_value)

            with psycopg2.connect(host=secrets["DB_HOST"], 
                                  database="incident_report", 
                                  user="db_admin", 
                                  password=secrets["DB_PASSWORD"]
                                  ) as conn:
                with conn.cursor() as cur:
                    query = "INSERT INTO incidents (incident_id, description, ai_severity, severity, confidence, image_url, needs_review, ai_reasoning, prompt_version, deadline, policies_applied, address, zip_code, data_source, transformation_log) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'SF_311_API', %s) ON CONFLICT (incident_id) DO UPDATE SET description = EXCLUDED.description, ai_severity = EXCLUDED.ai_severity, severity = EXCLUDED.severity, confidence = EXCLUDED.confidence, image_url = EXCLUDED.image_url, needs_review = EXCLUDED.needs_review, ai_reasoning = EXCLUDED.ai_reasoning, prompt_version = EXCLUDED.prompt_version, deadline = EXCLUDED.deadline, policies_applied = EXCLUDED.policies_applied, address = EXCLUDED.address, zip_code = EXCLUDED.zip_code, transformation_log = EXCLUDED.transformation_log"
                    cur.execute(query, (incident_id, description, ai_severity_value, severity_value, confidence_value, image_url, governed_result['needs_review'], reasoning_value, prompt_version, governed_result['deadline'], ','.join(governed_result['applied_policies']), address_string, zip_code, initial_log))
                    conn.commit()
        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON: {e}")

    return response_content

if __name__ == "__main__":
    start_http_server(9090)
    mcp.run(transport='sse', host="0.0.0.0", port=8000) 