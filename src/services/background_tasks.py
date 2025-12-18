"""Background tasks for Q&A system."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from src.services.outcome_tracker import OutcomeTracker
from src.settings import Settings

logger = logging.getLogger(__name__)


class BackgroundTaskScheduler:
    """Scheduler for background tasks."""

    def __init__(self, settings: Settings):
        """
        Initialize background task scheduler.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.outcome_tracker: Optional[OutcomeTracker] = None
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_execution_time: Optional[datetime] = None
        self._next_execution_time: Optional[datetime] = None
        self._execution_count = 0
        self._error_count = 0

    async def start(self) -> None:
        """Start the background task scheduler."""
        if self._running:
            logger.warning("Background task scheduler is already running")
            return

        if not self.settings.qa_background_check_enabled:
            logger.info("Background task scheduler is disabled in settings")
            return

        self._running = True
        self.outcome_tracker = OutcomeTracker(self.settings)
        
        # Calculate next execution time
        self._next_execution_time = datetime.utcnow()
        
        # Start the periodic task
        self._task = asyncio.create_task(self._run_periodic_tasks())
        logger.info(
            f"Background task scheduler started "
            f"(check interval: {self.settings.qa_background_check_interval_hours} hours)"
        )

    async def stop(self) -> None:
        """Stop the background task scheduler."""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Background task scheduler stopped")

    async def _run_periodic_tasks(self) -> None:
        """Run periodic background tasks."""
        # Run immediately on startup (after a short delay)
        await asyncio.sleep(10)  # Wait 10 seconds for app to fully start
        
        check_interval_seconds = self.settings.qa_background_check_interval_hours * 3600
        
        while self._running:
            try:
                self._last_execution_time = datetime.utcnow()
                self._execution_count += 1
                
                await self.check_auto_success_sessions()
                
                # Calculate next execution time
                self._next_execution_time = datetime.utcnow().replace(
                    microsecond=0
                ) + timedelta(seconds=check_interval_seconds)
                
            except Exception as e:
                self._error_count += 1
                logger.exception(f"Error in periodic background task: {e}")
                # Continue running even if there's an error
            
            # Wait for next check interval
            await asyncio.sleep(check_interval_seconds)

    async def check_auto_success_sessions(self, max_retries: int = 3) -> None:
        """
        Periodic task to check and auto-mark successful sessions.
        
        This task runs periodically and checks for sessions that:
        - Have been exported
        - Are older than qa_auto_success_days
        - Have no follow-up sessions
        - Don't already have an outcome status
        
        Args:
            max_retries: Maximum number of retries for failed operations
        """
        retry_count = 0
        
        while retry_count <= max_retries:
            try:
                logger.info("Starting auto-success check for sessions")
                
                session_ids = await self.outcome_tracker.get_sessions_for_auto_success_check()
                
                if not session_ids:
                    logger.info("No sessions found for auto-success check")
                    return

                logger.info(f"Found {len(session_ids)} session(s) to check for auto-success")

                success_count = 0
                error_count = 0

                for session_id in session_ids:
                    try:
                        # Double-check if should be marked as successful
                        should_mark = await self.outcome_tracker.check_auto_success(session_id)
                        
                        if should_mark:
                            await self.outcome_tracker.mark_session_outcome(
                                session_id=session_id,
                                outcome="successful",
                                determined_by="auto"
                            )
                            success_count += 1
                            logger.info(f"Auto-marked session {session_id} as successful")
                        else:
                            logger.debug(f"Session {session_id} does not meet auto-success criteria")
                    except Exception as e:
                        error_count += 1
                        logger.error(f"Error processing session {session_id} for auto-success: {e}")

                logger.info(
                    f"Auto-success check completed: {success_count} marked as successful, "
                    f"{error_count} errors"
                )
                
                # Success - break out of retry loop
                return

            except Exception as e:
                retry_count += 1
                if retry_count <= max_retries:
                    wait_time = 2 ** retry_count  # Exponential backoff
                    logger.warning(
                        f"Error in check_auto_success_sessions (attempt {retry_count}/{max_retries}): {e}. "
                        f"Retrying in {wait_time} seconds..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.exception(f"Error in check_auto_success_sessions after {max_retries} retries: {e}")
                    raise
    
    def get_status(self) -> dict:
        """
        Get status information about the background task scheduler.
        
        Returns:
            Dictionary with status information
        """
        return {
            "enabled": self.settings.qa_background_check_enabled,
            "running": self._running,
            "last_execution_time": self._last_execution_time.isoformat() if self._last_execution_time else None,
            "next_execution_time": self._next_execution_time.isoformat() if self._next_execution_time else None,
            "execution_count": self._execution_count,
            "error_count": self._error_count,
            "check_interval_hours": self.settings.qa_background_check_interval_hours,
            "auto_success_days": self.settings.qa_auto_success_days
        }

