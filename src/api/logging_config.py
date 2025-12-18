"""Centralized logging configuration for the API."""

import logging
import sys
import os
from typing import Optional
from logging.handlers import RotatingFileHandler


def sanitize_sensitive_data(data: dict) -> dict:
    """Remove sensitive fields from log data."""
    sensitive_keys = {'password', 'api_key', 'apiKey', 'token', 'authorization', 'authorization_header'}
    sanitized = {}
    for key, value in data.items():
        if any(sensitive in key.lower() for sensitive in sensitive_keys):
            sanitized[key] = '***REDACTED***'
        elif isinstance(value, dict):
            sanitized[key] = sanitize_sensitive_data(value)
        elif isinstance(value, list):
            sanitized[key] = [
                sanitize_sensitive_data(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            sanitized[key] = value
    return sanitized


class RequestIDFilter(logging.Filter):
    """Add request ID to log records."""
    
    def filter(self, record):
        # Request ID will be set by middleware via contextvars
        # If not set in extra, try to get from contextvar (lazy import to avoid circular dependency)
        if not hasattr(record, 'request_id'):
            try:
                from src.api.middleware import request_id_var
                record.request_id = request_id_var.get() or 'none'
            except (ImportError, AttributeError):
                # If middleware not loaded yet, use default
                record.request_id = getattr(record, 'request_id', 'none')
        return True


def setup_logging(log_level: Optional[str] = None) -> None:
    """
    Configure logging for the application.
    
    Args:
        log_level: Log level from environment (default: INFO)
    """
    # Get log level from environment or default to INFO
    if log_level is None:
        log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    
    # Convert string to logging level
    numeric_level = getattr(logging, log_level, logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()
    
    # Console handler with colored output (if colorama available)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(RequestIDFilter())
    root_logger.addHandler(console_handler)
    
    # File handler with rotation
    log_file = 'rag_agent.log'
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(RequestIDFilter())
    root_logger.addHandler(file_handler)
    
    # Set levels for noisy libraries
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    logging.info(f"Logging configured: level={log_level}, file={log_file}")

