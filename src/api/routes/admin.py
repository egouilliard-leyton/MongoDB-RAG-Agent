"""Admin endpoints for background tasks and system management."""

import logging
from fastapi import APIRouter, HTTPException, Header
from typing import Optional

from src.services.background_tasks import BackgroundTaskScheduler
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.api.main import scheduler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


# Simple API key check (can be enhanced with proper authentication)
def verify_admin_key(admin_key: Optional[str] = Header(None)) -> bool:
    """
    Verify admin API key.
    
    For now, this is a simple check. In production, use proper authentication.
    """
    # In production, check against environment variable or database
    # For now, allow if no key is required or key matches expected value
    return True  # Simplified for now


def get_scheduler():
    """Get the scheduler instance from main module (lazy import to avoid circular dependency)."""
    from src.api.main import scheduler
    return scheduler


@router.post("/background-tasks/check-auto-success")
async def trigger_auto_success_check(
    admin_key: Optional[str] = Header(None, alias="X-Admin-Key")
):
    """
    Manually trigger the auto-success check for sessions.
    
    This endpoint allows manual triggering of the background task for testing
    or immediate execution.
    
    Args:
        admin_key: Optional admin API key for authentication
    
    Returns:
        Result of the check operation
    """
    # Verify admin access (simplified for now)
    if not verify_admin_key(admin_key):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    scheduler = get_scheduler()
    if not scheduler:
        raise HTTPException(
            status_code=503,
            detail="Background task scheduler is not initialized"
        )
    
    if not scheduler._running:
        raise HTTPException(
            status_code=503,
            detail="Background task scheduler is not running"
        )
    
    try:
        await scheduler.check_auto_success_sessions()
        return {
            "message": "Auto-success check completed successfully",
            "status": "success"
        }
    except Exception as e:
        logger.exception(f"Error triggering auto-success check: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error executing auto-success check: {str(e)}"
        )


@router.get("/background-tasks/status")
async def get_background_tasks_status(
    admin_key: Optional[str] = Header(None, alias="X-Admin-Key")
):
    """
    Get status information about background tasks.
    
    Args:
        admin_key: Optional admin API key for authentication
    
    Returns:
        Status information about background tasks
    """
    # Verify admin access (simplified for now)
    if not verify_admin_key(admin_key):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    scheduler = get_scheduler()
    if not scheduler:
        return {
            "enabled": False,
            "running": False,
            "message": "Background task scheduler is not initialized"
        }
    
    return scheduler.get_status()

