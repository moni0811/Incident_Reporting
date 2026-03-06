FROM python:3.11-slim
WORKDIR /incident_report

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy both app.py AND static folder
COPY app.py .
COPY static/ ./static/

CMD ["python", "app.py"]