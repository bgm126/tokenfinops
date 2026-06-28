import logging
import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger(__name__)

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.perf_counter()
        
        # Capture basic details
        method = request.method
        path = request.url.path
        
        try:
            response = await call_next(request)
            duration = (time.perf_counter() - start_time) * 1000
            
            logger.info(
                f"{method} {path} - Status: {response.status_code} - Duration: {duration:.2f}ms"
            )
            return response
        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"{method} {path} - Failed with error: {e} - Duration: {duration:.2f}ms"
            )
            raise e
