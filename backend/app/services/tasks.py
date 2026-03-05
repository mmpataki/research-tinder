"""
Background task manager for long-running operations (scraping, scoring).
Uses asyncio tasks so the API stays responsive while work happens in background.
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class TaskManager:
    """Tracks background tasks so the UI can poll progress."""

    def __init__(self):
        self._task: Optional[asyncio.Task] = None
        self.status: str = "idle"  # idle | running | done | error
        self.message: str = ""
        self.started_at: Optional[datetime] = None
        self.finished_at: Optional[datetime] = None

    @property
    def is_running(self) -> bool:
        return self.status == "running"

    def get_status(self) -> dict:
        return {
            "status": self.status,
            "message": self.message,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }

    def start(self, coro, description: str = ""):
        if self.is_running:
            raise RuntimeError("A task is already running")

        self.status = "running"
        self.message = description
        self.started_at = datetime.utcnow()
        self.finished_at = None

        async def _wrapper():
            try:
                result_msg = await coro
                self.status = "done"
                self.message = result_msg or "Completed"
            except Exception as e:
                self.status = "error"
                self.message = str(e)
                logger.error(f"Background task failed: {e}")
            finally:
                self.finished_at = datetime.utcnow()

        self._task = asyncio.get_event_loop().create_task(_wrapper())


# Singleton
task_manager = TaskManager()
