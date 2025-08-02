from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from api.crud import router as crud_router
from api.router import router as routing_router
from core.logging_config import setup_logging, get_logger
import time
import uuid

# Initialize logging
setup_logging()
logger = get_logger(__name__)

app = FastAPI(title="PolySynergy Router", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    # Generate request ID for tracking
    request_id = str(uuid.uuid4())
    
    # Log request details
    start_time = time.time()
    logger.info(f"Request started - ID: {request_id}, Method: {request.method}, Path: {request.url.path}")
    
    # Add request ID to request state for use in other parts of the app
    request.state.request_id = request_id
    
    try:
        # Process request
        response = await call_next(request)
        
        # Calculate request duration
        duration = time.time() - start_time
        
        # Log response details
        logger.info(f"Request completed - ID: {request_id}, Status: {response.status_code}, Duration: {round(duration * 1000, 2)}ms")
        
        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        
        return response
        
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Request failed - ID: {request_id}, Error: {str(e)}, Duration: {round(duration * 1000, 2)}ms", exc_info=True)
        raise

@app.on_event("startup")
async def startup_event():
    logger.info("PolySynergy Router starting up...")
    logger.info(f"Logging level: {logger.level}")
    logger.info("Router ready to handle requests")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("PolySynergy Router shutting down...")

@app.get("/__internal/health")
def health():
    return {"ok": True}

app.include_router(crud_router, prefix="/__internal")
app.include_router(routing_router)
