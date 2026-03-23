import logging
import json
import datetime
import os
from shared.middleware import TRACE_ID_VAR

class JSONFormatter(logging.Formatter):
    """
    Custom formatter to output logs in JSON format.
    """
    def format(self, record):
        log_record = {
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "func_name": record.funcName,
            "trace_id": TRACE_ID_VAR.get(),  # Get the trace_id from context
        }

        # Add trace_id and incident_id if they exist in the extra context
        # if hasattr(record, "trace_id"):
        #    log_record["trace_id"] = record.trace_id
        if hasattr(record, "incident_id"):
            log_record["incident_id"] = record.incident_id
            
        # Capture exception info if available
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_record)

def get_logger(name: str):
    """
    Utility function to initialize and return a structured logger.
    """
    logger = logging.getLogger(name)
    
    # Set default log level (INFO) or get from environment
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logger.setLevel(log_level)

    # Prevent logs from bubbling up to the root logger if already configured
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        
    return logger
