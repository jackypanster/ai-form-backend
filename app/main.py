from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.api.v1 import api_router as api_v1_router # Ensure this import path is correct
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,  # Or load from settings: get_settings().log_level
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler() # Output to console
        # You can add FileHandler here for logging to a file
    ]
)
logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    openapi_url=f"/api/v1/openapi.json" # Or adjust path as needed
)

# CORS Middleware
if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.cors_origins],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Include API routers
app.include_router(api_v1_router, prefix="/api/v1")

# Global Exception Handler (optional, for unhandled exceptions)
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"status": "error", "message": "An unexpected internal server error occurred."},
    )

@app.on_event("startup")
async def startup_event():
    logger.info("Application startup complete.")
    logger.info(f"CORS origins allowed: {settings.cors_origins}")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Application shutdown complete.")

# Health check endpoint (optional)
@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok"}

logger.info("FastAPI application initialized.") 