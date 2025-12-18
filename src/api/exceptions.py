"""Custom exception classes for API error handling."""

from typing import Optional, Dict, Any


class APIException(Exception):
    """Base exception for all API errors."""
    
    def __init__(
        self,
        message: str,
        status_code: int = 500,
        detail: Optional[str] = None,
        error_type: Optional[str] = None
    ):
        """
        Initialize API exception.
        
        Args:
            message: Human-readable error message
            status_code: HTTP status code
            detail: Additional error details
            error_type: Error type identifier
        """
        self.message = message
        self.status_code = status_code
        self.detail = detail
        self.error_type = error_type or self.__class__.__name__
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for JSON response."""
        result = {
            "error": self.error_type,
            "message": self.message,
            "status_code": self.status_code
        }
        if self.detail:
            result["detail"] = self.detail
        return result


class ValidationError(APIException):
    """Exception for validation errors (400)."""
    
    def __init__(self, message: str, detail: Optional[str] = None):
        super().__init__(
            message=message,
            status_code=400,
            detail=detail,
            error_type="ValidationError"
        )


class NotFoundError(APIException):
    """Exception for resource not found errors (404)."""
    
    def __init__(self, resource_type: str, resource_id: Optional[str] = None):
        if resource_id:
            message = f"{resource_type} not found: {resource_id}"
        else:
            message = f"{resource_type} not found"
        super().__init__(
            message=message,
            status_code=404,
            error_type="NotFoundError"
        )


class ConflictError(APIException):
    """Exception for conflict errors (409)."""
    
    def __init__(self, message: str, detail: Optional[str] = None):
        super().__init__(
            message=message,
            status_code=409,
            detail=detail,
            error_type="ConflictError"
        )


class UnauthorizedError(APIException):
    """Exception for unauthorized access errors (401)."""
    
    def __init__(self, message: str = "Unauthorized access", detail: Optional[str] = None):
        super().__init__(
            message=message,
            status_code=401,
            detail=detail,
            error_type="UnauthorizedError"
        )


class InternalServerError(APIException):
    """Exception for internal server errors (500)."""
    
    def __init__(self, message: str = "Internal server error", detail: Optional[str] = None):
        super().__init__(
            message=message,
            status_code=500,
            detail=detail,
            error_type="InternalServerError"
        )


class ServiceUnavailableError(APIException):
    """Exception for service unavailable errors (503)."""
    
    def __init__(self, message: str = "Service unavailable", detail: Optional[str] = None):
        super().__init__(
            message=message,
            status_code=503,
            detail=detail,
            error_type="ServiceUnavailableError"
        )

