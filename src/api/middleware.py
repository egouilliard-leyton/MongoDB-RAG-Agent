"""Error handling and request logging middleware for FastAPI."""

import logging
import time
import uuid
from contextvars import ContextVar
from typing import Callable
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from bson.errors import InvalidId

from src.api.exceptions import APIException, ValidationError as APIValidationError, NotFoundError, InternalServerError
from src.api.logging_config import sanitize_sensitive_data

logger = logging.getLogger(__name__)

# Context variable for request ID
request_id_var: ContextVar[str] = ContextVar('request_id', default=None)


async def request_logging_middleware(request: Request, call_next: Callable) -> Response:
    """
    Request/response logging middleware.
    
    Logs:
    - Request method, path, query params
    - Request body (sanitized)
    - Response status, timing, size
    - Generates unique request ID for tracing
    """
    # Generate unique request ID
    request_id = str(uuid.uuid4())[:8]
    request_id_var.set(request_id)
    
    # Start timing
    start_time = time.time()
    
    # Get request details
    method = request.method
    path = request.url.path
    query_params = dict(request.query_params)
    
    # Read request body if available (for POST/PUT requests)
    # Note: We need to read and restore the body since FastAPI consumes it
    request_body = None
    body_bytes = None
    if method in ('POST', 'PUT', 'PATCH'):
        try:
            body_bytes = await request.body()
            if body_bytes:
                import json
                try:
                    request_body = json.loads(body_bytes.decode('utf-8'))
                except:
                    request_body = body_bytes.decode('utf-8', errors='replace')[:500]  # Limit size
        except Exception as e:
            logger.debug(f"Could not read request body: {e}")
    
    # Restore request body for FastAPI to consume
    async def receive():
        if body_bytes:
            return {'type': 'http.request', 'body': body_bytes}
        return await request._receive()
    
    # Replace request's receive method to restore body
    if body_bytes:
        request._receive = receive
    
    # Sanitize headers (remove sensitive data)
    headers = dict(request.headers)
    sanitized_headers = sanitize_sensitive_data(headers)
    
    # Log request
    logger.info(
        f"Request started: {method} {path}",
        extra={
            'request_id': request_id,
            'method': method,
            'path': path,
            'query_params': query_params,
            'headers': sanitized_headers,
            'body': sanitize_sensitive_data(request_body) if isinstance(request_body, dict) else request_body
        }
    )
    
    # Process request
    try:
        response = await call_next(request)
        
        # Calculate timing
        process_time = time.time() - start_time
        
        # Get response size (approximate)
        response_size = None
        if hasattr(response, 'body'):
            try:
                response_size = len(response.body) if response.body else 0
            except:
                pass
        
        # Log response
        logger.info(
            f"Request completed: {method} {path} -> {response.status_code}",
            extra={
                'request_id': request_id,
                'method': method,
                'path': path,
                'status_code': response.status_code,
                'process_time_ms': round(process_time * 1000, 2),
                'response_size': response_size
            }
        )
        
        # Add request ID to response headers
        response.headers['X-Request-ID'] = request_id
        
        return response
        
    except Exception as e:
        # Calculate timing even on error
        process_time = time.time() - start_time
        
        logger.error(
            f"Request failed: {method} {path} -> Exception",
            extra={
                'request_id': request_id,
                'method': method,
                'path': path,
                'process_time_ms': round(process_time * 1000, 2),
                'error': str(e),
                'error_type': type(e).__name__
            },
            exc_info=True
        )
        
        # Re-raise to let error handler middleware catch it
        raise


async def error_handler_middleware(request: Request, call_next: Callable) -> Response:
    """
    Global error handling middleware.
    
    Catches all exceptions and converts them to appropriate HTTP responses.
    """
    try:
        response = await call_next(request)
        return response
    except APIException as e:
        # Handle custom API exceptions
        request_id = request_id_var.get() or 'unknown'
        logger.warning(
            f"API exception: {e.message} (status: {e.status_code})",
            extra={
                'request_id': request_id,
                'method': request.method,
                'path': request.url.path,
                'status_code': e.status_code,
                'error_message': e.message
            }
        )
        response = JSONResponse(
            status_code=e.status_code,
            content=e.to_dict()
        )
        response.headers['X-Request-ID'] = request_id
        return response
    except RequestValidationError as e:
        # Handle FastAPI request validation errors
        errors = []
        for error in e.errors():
            field = " -> ".join(str(loc) for loc in error["loc"])
            errors.append(f"{field}: {error['msg']}")
        
        error_message = "Validation error"
        if errors:
            error_message = "; ".join(errors)
        
        logger.warning(f"Request validation error: {error_message}")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "ValidationError",
                "message": error_message,
                "detail": str(e.errors()),
                "status_code": 422
            }
        )
    except ValidationError as e:
        # Handle Pydantic validation errors
        errors = []
        for error in e.errors():
            field = " -> ".join(str(loc) for loc in error["loc"])
            errors.append(f"{field}: {error['msg']}")
        
        error_message = "Validation error"
        if errors:
            error_message = "; ".join(errors)
        
        logger.warning(f"Pydantic validation error: {error_message}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "ValidationError",
                "message": error_message,
                "detail": str(e.errors()),
                "status_code": 400
            }
        )
    except InvalidId as e:
        # Handle MongoDB ObjectId validation errors
        logger.warning(f"Invalid ObjectId: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "ValidationError",
                "message": f"Invalid ID format: {str(e)}",
                "status_code": 400
            }
        )
    except ValueError as e:
        # Handle ValueError (often from validation)
        error_msg = str(e)
        if "not found" in error_msg.lower():
            logger.warning(f"Resource not found: {error_msg}")
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "error": "NotFoundError",
                    "message": error_msg,
                    "status_code": 404
                }
            )
        else:
            logger.warning(f"Value error: {error_msg}")
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "error": "ValidationError",
                    "message": error_msg,
                    "status_code": 400
                }
            )
    except Exception as e:
        # Handle all other exceptions
        request_id = request_id_var.get() or 'unknown'
        logger.exception(
            f"Unhandled exception: {type(e).__name__}: {str(e)}",
            extra={
                'request_id': request_id,
                'method': request.method,
                'path': request.url.path,
                'error_type': type(e).__name__,
                'error_message': str(e)
            }
        )
        response = JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "InternalServerError",
                "message": "An unexpected error occurred",
                "detail": str(e) if logger.level <= logging.DEBUG else None,
                "status_code": 500,
                "request_id": request_id
            }
        )
        response.headers['X-Request-ID'] = request_id
        return response

