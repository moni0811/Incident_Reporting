import uuid
from contextvars import ContextVar
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request

# This variable is thread-safe and request-safe
TRACE_ID_VAR: ContextVar[str] = ContextVar("trace_id", default="no-trace")

# class TracingMiddleware(BaseHTTPMiddleware):
#     async def dispatch(self, request: Request, call_next):
#         # 1. Generate a unique ID for this specific request
#         trace_id = str(uuid.uuid4())
        
#         # 2. Set it in the context variable
#         token = TRACE_ID_VAR.set(trace_id)
        
#         try:
#             # 3. Process the request
#             response = await call_next(request)
            
#             # 4. Include the trace_id in the response header (great for debugging!)
#             response.headers["X-Trace-ID"] = trace_id
#             return response
#         finally:
#             # 5. Clean up after the request is finished
#             TRACE_ID_VAR.reset(token)
