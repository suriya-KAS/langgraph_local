"""
Main entry point for the FastAPI application
"""
import uvicorn
from src.api.routes import app
from utils.logger_config import get_logger

logger = get_logger(__name__)

if __name__ == "__main__":
    logger.info("Starting MySellerCentral Chatbot API server")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8502,
        workers=1,  # For development; increase for production
        log_level="info"
    )

