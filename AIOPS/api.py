import os
import requests
from fastapi import FastAPI, BackgroundTasks
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

# NEW: Import Resource
from opentelemetry.sdk.resources import Resource

# 1. Configure OpenTelemetry
# NEW: Define the service name explicitly
resource = Resource.create({"service.name": "ai-ops-tracer"})

# NEW: Pass the resource into the TracerProvider
provider = TracerProvider(resource=resource)

processor = BatchSpanProcessor(OTLPSpanExporter(endpoint="http://localhost:4317", insecure=True))
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

tracer = trace.get_tracer("ai-ops-tracer")

app = FastAPI(title="AI-Ops Pipeline")
FastAPIInstrumentor.instrument_app(app)

import os
import time
import pandas as pd
import re
import json
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import List
import uuid

from google import genai
from google.genai import types

# LangChain Imports
from langchain_community.document_loaders import DirectoryLoader, PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate



# Configuration: Use Environment Variable or hardcode for testing
# Change these lines at the top of api.py
# Remove the os.environ line entirely.
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
client = genai.Client(api_key=GEMINI_API_KEY)
# In your LangChain GoogleGenerativeAIEmbeddings initialization, explicitly pass the key:
embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-2", google_api_key=GEMINI_API_KEY)
MODEL_NAME = 'gemini-2.5-flash'
LOG_FILE_PATH = r"C:\AIOPS\Massive_Apache.txt"
RUNBOOK_DIR = r"C:\AIOPS\runbooks"

app = FastAPI(title="AI-Ops Incident Engine API")

import sqlite3

def init_db():
    """Initializes the SQLite database on startup."""
    conn = sqlite3.connect("incident_data.db")
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS incident_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id TEXT,
            original_severity TEXT,
            human_severity TEXT,
            comment TEXT,
            reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    print("✅ Database initialized.")

# Call this once at the top of your api.py
init_db()

# Structured Output Schema
class IncidentReport(BaseModel):
    severity: str = Field(description="Critical, High, Medium, or Low.")
    anomaly_type: str = Field(description="The nature of the anomaly.")
    source_ip: str = Field(description="The source IP address.")
    root_cause: str = Field(description="Most likely explanation.")
    evidence: List[str] = Field(description="Directly observed facts.")
    confidence: str = Field(description="High, Medium, or Low.")
    recommended_actions: List[str] = Field(description="Operational actions.")

def ingest_apache_log(file_path):
    log_pattern = re.compile(r'^\[([^\]]+)\]\s+\[([^\]]+)\]\s+(?:\[client\s+([^\]]+)\]\s+)?(.*)$')
    parsed_logs = []
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            match = log_pattern.match(line.strip())
            if match:
                parsed_logs.append({
                    # NEW: Capture the severity level (e.g., 'error', 'info')
                    'level': match.group(2).lower() if match.group(2) else 'info',
                    'client_ip': match.group(3) if match.group(3) else 'unknown',
                    'message': match.group(4).strip()
                })
    return pd.DataFrame(parsed_logs)

def setup_langchain_knowledge_base():
    persist_directory = r"E:\Resume\chroma_db"
    
    # FIX: Explicitly use the GEMINI_API_KEY variable here
    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-2", 
        google_api_key=GEMINI_API_KEY
    )
    
    print(f"🔍 Searching for runbooks in: {RUNBOOK_DIR}")
    loader = DirectoryLoader(RUNBOOK_DIR, glob="**/*.pdf", loader_cls=PyPDFLoader)
    docs = loader.load()
    
    if not docs:
        raise ValueError(f"CRITICAL: No documents found in {RUNBOOK_DIR}!")
    
    print(f"✅ Found {len(docs)} document(s).")

    if os.path.exists(persist_directory):
        return Chroma(persist_directory=persist_directory, embedding_function=embeddings).as_retriever()
    
    splits = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100).split_documents(docs)
    
    # FIX: Pass the correct embeddings object here
    return Chroma.from_documents(
        documents=splits, 
        embedding=embeddings, 
        persist_directory=persist_directory
    ).as_retriever()
    
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL") # Add this to your environment variables

def send_slack_alert(report: dict):
    """Pushes High/Critical incidents to Slack via Webhook."""
    if not SLACK_WEBHOOK_URL:
        print("Warning: SLACK_WEBHOOK_URL not set. Skipping alert.")
        return

    # Using Slack Block Kit for clean, enterprise-grade formatting
    slack_payload = {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🚨 {report['severity'].upper()} Incident Detected",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Type:*\n{report['anomaly_type']}"},
                    {"type": "mrkdwn", "text": f"*Source IP:*\n`{report['source_ip']}`"}
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Recommended Action:*\n{report.get('recommended_actions', 'N/A')}"
                }
            }
        ]
    }

    try:
        response = requests.post(SLACK_WEBHOOK_URL, json=slack_payload, timeout=5)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Failed to send Slack alert: {e}")

class AnomalyDetectionAgent:
    def __init__(self, logs_df):
        self.logs = logs_df

    def get_evidence(self):
        # 1. Assign a point value to each type of log
        severity_map = {
            "emerg": 100, "alert": 100, "crit": 100, "error": 80, 
            "warn": 50, "notice": 10, "info": 1, "debug": 1
        }
        
        # 2. Map the points to a new column
        self.logs["severity"] = self.logs["level"].map(severity_map).fillna(1)
        
        # 3. Group by IP and Message, counting them up and keeping the max severity
        anomalies = self.logs.groupby(["client_ip", "message"]).agg(
            count=("message", "size"),
            severity_score=("severity", "max")
        ).reset_index()
        
        # 4. Multiply count by severity to find the true priority
        anomalies["priority"] = anomalies["count"] * anomalies["severity_score"]
        
        # 5. Sort by priority instead of just count
        top_anomalies = anomalies.sort_values(by="priority", ascending=False).head(3)
        
        # Return the clean evidence to the AI (dropping the math columns so it doesn't get confused)
        return top_anomalies[["client_ip", "message", "count"]].to_dict("records")

class RootCauseAnalysisAgent:
    def __init__(self, retriever):
        self.retriever = retriever
        self.llm = ChatGoogleGenerativeAI(
            model=MODEL_NAME, 
            temperature=0.0,
            google_api_key=GEMINI_API_KEY 
        )

    def investigate(self, evidence_data):
        print("🧠 RCA Agent: Reading the retrieved context...")
        
        # FIX: Convert the list of dictionaries into a plain text string
        evidence_string = json.dumps(evidence_data, indent=2)
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an Enterprise SRE AI.
            Rules: 
            1. Use ONLY provided evidence and context.
            2. Extract severity, anomaly_type, and source_ip from the provided logs.
            3. Never invent threat intel. 
            4. Distinguish FACTS from INFERENCES.
            5. Never use words like 'attack', 'malicious', 'botnet', or 'hacker' unless explicitly supported by the context.
            Confidence Rules: High (Direct evidence), Medium (Strong pattern), Low (Insufficient evidence).
            Retrieved Context: {context}"""),
            ("human", "Evidence:\n{evidence}") # <--- THIS IS THE MISSING LINE
        ])
        
        structured_llm = self.llm.with_structured_output(IncidentReport)
        
        # We also convert it to a string here for the retriever to search the database
        docs = self.retriever.invoke(str(evidence_data))
        context = "\n".join([doc.page_content for doc in docs[:2]])
        
        print("🧠 RCA Agent: Generating the final JSON report...")
        
        # FIX: Pass the 'evidence_string' instead of the raw Python list
        response = structured_llm.invoke(prompt.invoke({
            "context": context, 
            "evidence": evidence_string
        }))
        
        return response.dict()

@app.post("/api/v1/run-diagnostic")
def run_diagnostic_pipeline():
    print("▶️ Step 1: Starting Diagnostic Pipeline...")
    start_time = time.time()
    
    df = ingest_apache_log(LOG_FILE_PATH)
    print("▶️ Step 2: Apache Logs ingested successfully.")
    
    retriever = setup_langchain_knowledge_base()
    print("▶️ Step 3: Knowledge Base is ready.")
    
    evidence = AnomalyDetectionAgent(df).get_evidence()
    print(f"▶️ Step 4: Evidence extracted -> {evidence}")
    
    remediation = RootCauseAnalysisAgent(retriever).investigate(evidence)
    print("▶️ Step 5: RCA Complete! Sending report to browser.")
    
    return {"status": "success", "latency": round(time.time() - start_time, 2), "report": remediation}
    
@app.post("/analyze_logs")
async def analyze_logs(background_tasks: BackgroundTasks):
    start_time = time.time()
    incident_id = str(uuid.uuid4()) # Generate unique ID
    
    # 1. TRACE THE DETERMINISTIC PANDAS MATH
    with tracer.start_as_current_span("pandas_anomaly_detection") as span:
        print("▶️ Step 1: Parsing and analyzing logs with Pandas...")
        
        # THIS is your "actual data processing code"! 
        # We are calling the real functions you built.
        df = ingest_apache_log(LOG_FILE_PATH) 
        evidence = AnomalyDetectionAgent(df).get_evidence()
        
        # Add a real metric to Jaeger showing how many log rows we processed
        span.set_attribute("logs.processed", len(df)) 
        
    # 2. TRACE THE RAG & GEMINI API CALL
    with tracer.start_as_current_span("gemini_rca_generation") as span:
        print("▶️ Step 2: Running RAG and generating report with Gemini...")
        
        # THIS is your actual Gemini calling code!
        retriever = setup_langchain_knowledge_base()
        remediation = RootCauseAnalysisAgent(retriever).investigate(evidence)
        
        span.set_attribute("model", "gemini-2.5-flash")

    print("▶️ Step 3: RCA Complete! Sending report to browser.")
    
    # Trigger Slack alert asynchronously if needed
    if remediation.get("severity") in ["High", "Critical"]:
        background_tasks.add_task(send_slack_alert, remediation)
        
    return {
        "incident_id": incident_id,
        "status": "success", 
        "latency": round(time.time() - start_time, 2), 
        "report": remediation
    }
    
class Feedback(BaseModel):
    incident_id: str  # Now mandatory
    human_severity: str
    comment: str = ""
    
@app.post("/api/v1/feedback")
def submit_feedback(fb: Feedback):
    # 1. Save to DB
    conn = sqlite3.connect("incident_data.db")
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO incident_feedback (incident_id, human_severity, comment) VALUES (?, ?, ?)",
        (fb.incident_id, fb.human_severity, fb.comment)
    )
    conn.commit()
    conn.close()

    # 2. Trigger Updated Slack Alert if needed
    if fb.human_severity in ["High", "Critical"]:
        update_msg = {
            "severity": fb.human_severity,
            "anomaly_type": "Human Override/Correction",
            "source_ip": "N/A (Feedback)",
            "recommended_actions": f"Feedback provided: {fb.comment}"
        }
        send_slack_alert(update_msg)

    return {"status": "success", "message": "Feedback recorded and alert sent."}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)