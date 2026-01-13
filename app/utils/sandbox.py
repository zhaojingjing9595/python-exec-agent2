"""
Simple execution sandbox for isolated code execution.
"""
import os
import tempfile
import shutil
import logging
from typing import Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class ExecutionSandbox:
    """
    Simple execution sandbox that provides an isolated directory for code execution.
    """
    
    def __init__(self, execution_id: Optional[str] = None):
        """
        Initialize the execution sandbox.
        
        Args:
            execution_id: Optional execution identifier for the sandbox directory name
        """
        self.execution_id = execution_id or "exec"
        self.work_dir: Optional[str] = None
        self._created = False
    
    def create(self) -> str:
        """
        Create the sandbox directory.
        
        Returns:
            Path to the sandbox directory
        """
        if not self._created:
            self.work_dir = tempfile.mkdtemp(prefix=f"{self.execution_id}_")
            self._created = True
            logger.debug(f"Created execution sandbox: {self.work_dir}")
        return self.work_dir
    
    def cleanup(self):
        """Clean up the sandbox directory."""
        if self.work_dir and os.path.exists(self.work_dir):
            try:
                shutil.rmtree(self.work_dir, ignore_errors=True)
                logger.debug(f"Cleaned up execution sandbox: {self.work_dir}")
            except Exception as e:
                logger.warning(f"Failed to cleanup sandbox {self.work_dir}: {e}")
            finally:
                self.work_dir = None
                self._created = False
    
    def __enter__(self):
        """Context manager entry."""
        return self.create()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.cleanup()
    
    def __del__(self):
        """Destructor to ensure cleanup."""
        if self._created:
            self.cleanup()


@contextmanager
def execution_sandbox(execution_id: Optional[str] = None):
    """
    Context manager for creating an execution sandbox.
    
    Usage:
        with execution_sandbox("my_exec") as sandbox_dir:
            # Code executes in sandbox_dir
            pass
        # Sandbox is automatically cleaned up
    
    Args:
        execution_id: Optional execution identifier
        
    Yields:
        Path to the sandbox directory
    """
    sandbox = ExecutionSandbox(execution_id)
    try:
        yield sandbox.create()
    finally:
        sandbox.cleanup()

