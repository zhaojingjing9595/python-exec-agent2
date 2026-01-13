"""
Main entry point for the application.
"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.routes import execution, general

# Configure logging
# Log to both console and file
log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
date_format = "%Y-%m-%d %H:%M:%S"

# Create logs directory if it doesn't exist
import os
os.makedirs("logs", exist_ok=True)

# Configure logging with both file and console handlers
logging.basicConfig(
    level=logging.INFO,
    format=log_format,
    datefmt=date_format,
    handlers=[
        logging.FileHandler("logs/app.log", encoding="utf-8"),
        logging.StreamHandler()  # Console output
    ]
)

logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(
    title="Python Execution Agent",
    description="A minimal execution agent that can receive Python code, run it safely in an isolated environment and return output and errors.",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(general.router)
app.include_router(execution.router)


def main():
    """Main function to run the application."""
    logger.info("Starting Python Execution Agent...")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )


if __name__ == "__main__":
    main()

