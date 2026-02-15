"""
Logging Configuration Module
Sets up centralized logging for the entire application
"""
import logging
import os
from datetime import datetime

# Create logs directory if it doesn't exist
LOG_FILE = f"{datetime.now().strftime('%m_%d_%Y_%H_%M_%S')}.log"
logs_path = os.path.join(os.getcwd(), "logs")
os.makedirs(logs_path, exist_ok=True)

LOG_FILE_PATH = os.path.join(logs_path, LOG_FILE)

# Common log format
LOG_FORMAT = "[ %(asctime)s ] %(lineno)d %(name)s - %(levelname)s - %(message)s"

# Configure file logging (all INFO and above go to file)
logging.basicConfig(
    filename=LOG_FILE_PATH,
    format=LOG_FORMAT,
    level=logging.INFO
)

# Add a separate console handler that only emits ERROR (and above) to stderr.
# This ensures production/docker captures only error logs while keeping full
# logs in the log file.
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.ERROR)
console_handler.setFormatter(logging.Formatter(LOG_FORMAT))

root_logger = logging.getLogger()
# Avoid adding duplicate *console* handlers (FileHandler is also a StreamHandler,
# so we check the concrete type, not isinstance).
if not any(type(h) is logging.StreamHandler for h in root_logger.handlers):
    root_logger.addHandler(console_handler)

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)

