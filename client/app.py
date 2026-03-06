import json
from fastapi.params import Depends
from mcp import ClientSession
from mcp.client.sse import sse_client
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import psycopg2
from fastapi.staticfiles import StaticFiles
import os
from datetime import datetime, timedelta
from jose import JWTError, jwt # type: ignore
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

#SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def read_secret(path):
    with open(path, "r") as f:
        return f.read().strip()
    
SECRET_PATH = "/etc/secret"
CONFIG_PATH = "/etc/config"

secrets = {
    "DB_HOST": read_secret(f"{SECRET_PATH}/DB_HOST"),
    "DB_NAME": read_secret(f"{SECRET_PATH}/DB_NAME"),
    "DB_USER": read_secret(f"{SECRET_PATH}/DB_USER"),
    "DB_PASSWORD": read_secret(f"{SECRET_PATH}/DB_PASSWORD"),
    "ADMIN_PASSWORD": read_secret(f"{SECRET_PATH}/ADMIN_PASSWORD"),
    "SECRET_KEY": read_secret(f"{SECRET_PATH}/SECRET_KEY") 
}

config = {
    "ESCALATION_AGENT_URL": read_secret(f"{CONFIG_PATH}/ESCALATION_AGENT_URL")
}
SECRET_KEY = secrets["SECRET_KEY"]

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

app=FastAPI()

@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    if form_data.username == "admin" and form_data.password == secrets["ADMIN_PASSWORD"]:
        access_token = create_access_token(data={"sub": form_data.username})
        return {"access_token": access_token, "token_type":  "bearer"}
    raise HTTPException(status_code=400, detail="Incorrect username or password")

@app.get("/health/live")
async def liveness():
    return {"status" : "alive"}

@app.get("/health/ready")
async def readiness():
    try:
        conn = psycopg2.connect(
            host=secrets["DB_HOST"],
            database=secrets["DB_NAME"],
            user=secrets["DB_USER"],
            password=secrets["DB_PASSWORD"],
            connect_timeout=3
        )
        conn.close()
        return {"status":"ready"}
    except Exception as e:
        raise HTTPException(status_code=503, details="DB Unreachable")



def get_current_user(token: str = Depends(oauth2_scheme)):
    credetails_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"})
    
    try:
        payload=jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credetails_exception
        return  username
    except JWTError:
        raise credetails_exception
         

class IncidentInput(BaseModel):
    description: str
    incident_id: str
    address: str | None = None
    image_url: str | None = None



@app.post("/report")
async def report_and_decide_escalation(data: IncidentInput):
    print('Starting report_and_decide_escalation')
    #url = "http://escalation-agent-service:80/sse"
    base_url = config["ESCALATION_AGENT_URL"]
    url = f"{base_url}/sse"
    print(f"Using Escalation Agent URL: {url}")
    try:
        async with sse_client(url) as (read,write):
            async with ClientSession (read,write) as session:
                await session.initialize()
                print('Calling tool')
                #result=await session.call_tool("decide_escalation", arguments={"description": "There is a massive sinkhole blocking traffic on Main Street", "incident_id": "INC_001"})
                #result=await session.call_tool("decide_escalation", arguments={"description": "There is a small  on 2nd Street in Greek Country", "incident_id": "INC_002"})
                result=await session.call_tool("decide_escalation", arguments={"description": data.description, "incident_id": data.incident_id, "address": data.address, "image_url": data.image_url})
                print('Result from tool call: ', result)
                # 1. Get the raw JSON string
                raw_json_string = result.content[0].text

                # 2. Convert back to a dictionary so you can access fields
                decision_data = json.loads(raw_json_string)
                print(f"✅ Decision made for {data.incident_id}: {decision_data}")
                return decision_data    
                
                #return {
                #    "status": "received", 
                #    "incident_id": data.incident_id,
                #    "agent_decision": decision_text
                #    }

    except Exception as e:
        print(f"❌ Error communicating with Agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/incidents")
def list_incidents(current_user: str = Depends(get_current_user)):
    conn = psycopg2.connect(
        host=secrets["DB_HOST"],
        database=secrets["DB_NAME"],
        user=secrets["DB_USER"],
        password=secrets["DB_PASSWORD"]
    )
    cur = conn.cursor()
    cur.execute("""
        SELECT incident_id, description, severity, confidence, 
               image_url, created_at, human_reviewed, needs_review , ai_reasoning, prompt_version
        FROM incidents 
        ORDER BY created_at DESC 
        LIMIT 100
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    
    return [{
        "incident_id": r[0],
        "description": r[1],
        "severity": r[2],
        "confidence": r[3],
        "image_url": r[4],
        "created_at": r[5].isoformat() if r[5] else None,
        "human_reviewed": r[6] if len(r) > 6 else False,
        "needs_review": r[7] if len(r) > 7 else False,
        "ai_reasoning":r[8]
    } for r in rows]


@app.get("/api/incidents/{incident_id}")
def get_incident(incident_id: str, current_user: str = Depends(get_current_user)):

    conn = psycopg2.connect(
        host=secrets["DB_HOST"],
        database=secrets["DB_NAME"],
        user=secrets["DB_USER"],
        password=secrets["DB_PASSWORD"]
    )

    cur = conn.cursor()

    cur.execute(
        """
        SELECT incident_id, description, severity, needs_review, policies_applied, created_at, deadline
        FROM incidents
        WHERE incident_id = %s
        """,
        (incident_id,)
    )

    row = cur.fetchone()

    cur.close()
    conn.close()

    if not row:
        return {"incident_id": None,
        "description": None,
        "severity": None,
        "needs_review": None,
        "status": "Not processed",
        "policies_applied": None,
        "created_at": None,
        "deadline": None}

    return {
        "incident_id": row[0],
        "description": row[1],
        "severity": row[2],
        "needs_review": row[3],
        "status": "processed",
        "policies_applied": row[4],
        "created_at": row[5],
        "deadline": row[6]
    }

# NEW: Approve incident
@app.post("/api/incidents/{incident_id}/approve")
def approve_incident(incident_id: str, current_user: str = Depends(get_current_user) ):
    conn = psycopg2.connect(
        host=secrets["DB_HOST"],
        database=secrets["DB_NAME"],
        user=secrets["DB_USER"],
        password=secrets["DB_PASSWORD"]
    )
    cur = conn.cursor()
    cur.execute("""
        UPDATE incidents 
        SET human_reviewed = TRUE, needs_review = FALSE 
        WHERE incident_id = %s
    """, (incident_id,))
    conn.commit()
    cur.close()
    conn.close()
    return {"status": "approved"}

# NEW: Reject incident  
@app.post("/api/incidents/{incident_id}/reject")
def reject_incident(incident_id: str, current_user: str = Depends(get_current_user)):
    conn = psycopg2.connect(
        host=secrets["DB_HOST"],
        database=secrets["DB_NAME"],
        user=secrets["DB_USER"],
        password=secrets["DB_PASSWORD"]
    )
    cur = conn.cursor()
    cur.execute("""
        UPDATE incidents 
        SET needs_review = TRUE 
        WHERE incident_id = %s
    """, (incident_id,))
    conn.commit()
    cur.close()
    conn.close()
    return {"status": "rejected"}

# NEW: Reclassify and Approve incident
@app.post("/api/incidents/{incident_id}/reclassify")
def reclassify_incident(incident_id: str, payload: dict, current_user: str = Depends(get_current_user)):
    new_severity = payload.get("severity")
    reviewer_notes = payload.get("reviewer_notes", "Manual human reclassification")
    actor = current_user

    conn = psycopg2.connect(
        host=secrets["DB_HOST"],
        database=secrets["DB_NAME"],
        user=secrets["DB_USER"],
        password=secrets["DB_PASSWORD"]
    )
    cur = conn.cursor()

    cur.execute("SELECT transformation_log FROM incidents WHERE incident_id = %s", (incident_id,))
    existing_log = cur.fetchone()[0] or ""

    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    new_entry = f"[{timestamp}] HUMAN_OVERRIDE to {new_severity} by {actor} (Note: {reviewer_notes})\n"
    updated_log = existing_log + new_entry

    # Update both the severity AND the review flags
    cur.execute("""
        UPDATE incidents 
        SET severity = %s, human_reviewed = TRUE, needs_review = FALSE, reviewer_notes = %s, transformation_log = %s
        WHERE incident_id = %s
    """, (new_severity, reviewer_notes, updated_log, incident_id,))
    conn.commit()
    cur.close()
    conn.close()
    
@app.post("/api/incidents/performancestats")
def get_performance_stats(current_user: str = Depends(get_current_user)):
    conn = psycopg2.connect(
        host=secrets["DB_HOST"],
        database=secrets["DB_NAME"],
        user=secrets["DB_USER"],
        password=secrets["DB_PASSWORD"]
    )
    cur = conn.cursor()
    cur.execute("""
       SELECT 
    prompt_version,
    COUNT(*) AS total_incidents,
    COUNT(*) FILTER (WHERE severity = ai_severity) AS matched_count,
    ROUND(
        (COUNT(*) FILTER (WHERE severity = ai_severity) * 100.0) / COUNT(*), 
        2
    ) AS accuracy_percentage
FROM incidents
WHERE human_reviewed = TRUE
GROUP BY prompt_version
ORDER BY prompt_version DESC;
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    
    return [{"version": r[0],
             "total_incidents": r[1],
             "matched_count": r[2],
             "accuracy_percentage": float(r[3])} for r in rows]

@app.get("/api/governance/drift_check")
def check_drift(prompt_version: str = "v1.2.0", current_user: str = Depends(get_current_user)):
    conn = psycopg2.connect(
        host=secrets["DB_HOST"],
        database=secrets["DB_NAME"],
        user=secrets["DB_USER"],
        password=secrets["DB_PASSWORD"]
    )
    cur = conn.cursor()
    cur.execute("""
        SELECT 
            COUNT(*) FILTER (WHERE severity = ai_severity) AS drift_count
            FROM (SELECT severity, ai_severity FROM incidents 
                    WHERE human_reviewed = TRUE AND prompt_version = %s
                    ORDER BY created_at ASC LIMIT 50) subquery;
    """, (prompt_version,))
    baseline_acc = cur.fetchone()[0]/50 or 0
    
    cur.execute("""
                SELECT 
            COUNT(*) FILTER (WHERE severity = ai_severity) AS drift_count
            FROM (SELECT severity, ai_severity FROM incidents 
                    WHERE human_reviewed = TRUE AND prompt_version = %s
                    ORDER BY created_at DESC LIMIT 50) subquery;
    """, (prompt_version,))
    current_acc = cur.fetchone()[0]/50 or 0
    cur.close()
    conn.close()

    drift_detected = (baseline_acc - current_acc) > 0.10 if baseline_acc > 0 else False
    return {"version": prompt_version, 
            "baseline_accuracy": round(baseline_acc,2),
             "current_accuracy": round(current_acc,2),
             "drift_detected": drift_detected,
             "status":"🚨 DRIFT ALERT" if drift_detected else "✅ STABLE"}


@app.get("/api/governance/bias_check")
def check_geographicbias(current_user: str = Depends(get_current_user)):
    conn = psycopg2.connect(
        host=secrets["DB_HOST"],
        database=secrets["DB_NAME"],
        user=secrets["DB_USER"],
        password=secrets["DB_PASSWORD"]
    )

    cur = conn.cursor()
    cur.execute("""
        SELECT 
            zip_code, COUNT(*) AS Total, 
            (COUNT(*) FILTER (WHERE severity = ai_severity)/NULLIF(COUNT(*), 0)) * 100 AS Accuracy_Percentage
        FROM incidents
        WHERE human_reviewed = TRUE
        GROUP BY zip_code
        HAVING COUNT(*) > 1
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        return {
            "bias_detected": False, 
            "status": "⏳ Awaiting Human Review Data", 
            "bias_gap_percentage": 0,
            "neighborhoods_stats": []
        }
    
    neighborhood_stats = [{"zip_code": r[0], "total_incidents": r[1], "accuracy": round(r[2],2)} for r in rows]
    accuracies = [r[2] for r in rows if r[2] is not None]
    max_acc = max(accuracies) if accuracies else 0
    min_acc = min(accuracies) if accuracies else 0
    bias_gap = max_acc - min_acc
    bias_detected = bias_gap > 20

    return {
        "neighborhoods_stats": neighborhood_stats,
        "bias_gap_percentage" : round(bias_gap,2),
        "bias_detected": bias_detected,
        "status": "🚨 BIAS ALERT" if bias_detected else "✅ NO SIGNIFICANT BIAS"
    }
             
# 1. Get the directory where app.py is located
current_dir = os.path.dirname(os.path.realpath(__file__))

# 2. Build the absolute path to the 'static' folder
static_dir = os.path.join(current_dir, "static")

# 3. Mount it using the absolute path
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)