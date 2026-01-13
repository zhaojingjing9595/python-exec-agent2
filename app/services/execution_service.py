"""
Unified execution service for safe, isolated Python code execution.
Combines execution engine and service layer with sandbox-based isolation.
"""
import asyncio
import logging
import os
import signal
import subprocess
import time
import uuid
from dataclasses import dataclass
from typing import Optional
import resource

from app.models.schema import CodeExecutionRequest, CodeExecutionResponse, ExecutionStatus
from app.utils.sandbox import ExecutionSandbox

logger = logging.getLogger(__name__)


@dataclass
class ExecutionConfig:
    """Configuration for code execution."""
    timeout: int = 5
    max_memory_mb: int = 128  # Maximum memory in MB
    max_cpu_time: int = 10  # Maximum CPU time in seconds
    python_executable: str = "python3"
    enable_filesystem_isolation: bool = True
    max_concurrent_executions: int = 10


@dataclass
class ExecutionResult:
    """Result of code execution."""
    stdout: str
    stderr: str
    return_code: int
    execution_time: float
    timed_out: bool = False


class ExecutionService:
    """
    Unified execution service with process isolation, resource limits, timeout protection,
    and sandbox-based filesystem isolation.
    """
    
    def __init__(
        self,
        python_executable: str = "python3",
        max_memory_mb: int = 128,
        max_cpu_time: int = 10,
        max_concurrent: int = 10,
        enable_filesystem_isolation: bool = True
    ):
        """
        Initialize the execution service.
        
        Args:
            python_executable: Path to Python executable
            max_memory_mb: Maximum memory per execution in MB
            max_cpu_time: Maximum CPU time per execution in seconds
            max_concurrent: Maximum concurrent executions
            enable_filesystem_isolation: Enable filesystem isolation via sandbox
        """
        self.config = ExecutionConfig(
            python_executable=python_executable,
            max_memory_mb=max_memory_mb,
            max_cpu_time=max_cpu_time,
            max_concurrent_executions=max_concurrent,
            enable_filesystem_isolation=enable_filesystem_isolation
        )
        self.semaphore = asyncio.Semaphore(self.config.max_concurrent_executions)
        self.active_executions: dict[str, asyncio.Task] = {}
        
        logger.info(
            f"ExecutionService initialized: python={python_executable}, "
            f"max_memory={max_memory_mb}MB, max_cpu_time={max_cpu_time}s, "
            f"max_concurrent={max_concurrent}, filesystem_isolation={enable_filesystem_isolation}"
        )
    
    async def execute_code(
        self,
        request: CodeExecutionRequest
    ) -> CodeExecutionResponse:
        """
        Execute Python code safely in an isolated environment.
        
        Args:
            request: Code execution request
            
        Returns:
            Code execution response with results
        """
        execution_id = str(uuid.uuid4())[:8]
        logger.info(f"[{execution_id}] Executing code with timeout: {request.timeout}s")
        
        # Acquire semaphore to limit concurrent executions
        async with self.semaphore:
            try:
                start_time = time.time()
                
                # Create sandbox if filesystem isolation is enabled
                sanbox = None
                work_dir = None
                if self.config.enable_filesystem_isolation:
                    sandbox = ExecutionSandbox(execution_id)
                    work_dir = sandbox.create()
                    logger.debug(f"[{execution_id}] Created sandbox: {work_dir}")
                
                try:
                    # Run in executor to avoid blocking event loop
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(
                        None,
                        self._run_subprocess,
                        request.code,
                        work_dir,
                        execution_id,
                        request.timeout
                    )
                    result.execution_time = time.time() - start_time
                finally:
                    # Cleanup sandbox
                    if sandbox:
                        sandbox.cleanup()
                        logger.debug(f"[{execution_id}] Cleaned up sandbox")
                
                # Determine status
                if result.timed_out:
                    status = ExecutionStatus.TIMEOUT
                elif result.return_code == 0:
                    status = ExecutionStatus.SUCCESS
                elif result.return_code == -1:
                    status = ExecutionStatus.FAILED
                else:
                    status = ExecutionStatus.ERROR
                
                response = CodeExecutionResponse(
                    status=status,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    execution_time=result.execution_time,
                    return_code=result.return_code if result.return_code != -1 else None
                )
                
                logger.info(
                    f"[{execution_id}] Execution completed: status={status}, time={result.execution_time:.3f}s"
                )
                
                return response
                
            except asyncio.TimeoutError:
                logger.warning(f"[{execution_id}] Execution timed out after {request.timeout}s")
                return CodeExecutionResponse(
                    status=ExecutionStatus.TIMEOUT,
                    stdout="",
                    stderr=f"Execution timed out after {request.timeout} seconds",
                    execution_time=request.timeout,
                    return_code=None
                )
            except Exception as e:
                logger.error(
                    f"[{execution_id}] Execution service error: {str(e)}",
                    exc_info=True
                )
                return CodeExecutionResponse(
                    status=ExecutionStatus.FAILED,
                    stdout="",
                    stderr=f"Execution service error: {str(e)}",
                    execution_time=0.0,
                    return_code=None
                )
    
    def _run_subprocess(
        self,
        code: str,
        work_dir: Optional[str],
        execution_id: str,
        timeout: int
    ) -> ExecutionResult:
        """
        Run code in subprocess with resource limits, timeout, and isolation.
        This runs in an executor thread to avoid blocking the event loop.
        """
        start_time = time.time()
        process = None
        
        try:
            # Prepare minimal environment (filter out sensitive variables)
            env = {
                "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                "HOME": "/tmp",  # Set safe HOME
                "TMPDIR": work_dir or "/tmp",
                "TMP": work_dir or "/tmp",
                "TEMP": work_dir or "/tmp",
                "PYTHONUNBUFFERED": "1",
                "PYTHONDONTWRITEBYTECODE": "1",
                # Keep Python-related paths if they exist
            }
            # Only preserve safe Python-related environment variables
            safe_python_vars = ["PYTHONPATH", "PYTHONHOME"]
            for var in safe_python_vars:
                if var in os.environ:
                    env[var] = os.environ[var]
            
            # Set resource limits function (Unix only)
            def set_limits():
                try:
                    max_memory_bytes = self.config.max_memory_mb * 1024 * 1024
                    resource.setrlimit(resource.RLIMIT_AS, (max_memory_bytes, max_memory_bytes))
                    resource.setrlimit(resource.RLIMIT_CPU, (self.config.max_cpu_time, self.config.max_cpu_time))
                    # Try to set file descriptor limit, but handle if it fails
                    try:
                        current_soft, current_hard = resource.getrlimit(resource.RLIMIT_NOFILE)
                        desired = min(64, current_hard)
                        if desired >= current_soft:
                            resource.setrlimit(resource.RLIMIT_NOFILE, (desired, current_hard))
                    except (ValueError, OSError):
                        pass  # Skip if can't set
                except Exception as e:
                    logger.debug(f"Resource limits not set: {e}")
            
            # Create subprocess with isolation
            if os.name != 'nt':
                # Unix: Use preexec_fn to set resource limits before exec
                process = subprocess.Popen(
                    [self.config.python_executable, "-c", code],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=env,
                    cwd=work_dir,
                    preexec_fn=set_limits,
                    close_fds=True
                )
                # Create new process group after process starts
                try:
                    os.setpgid(process.pid, process.pid)
                except (OSError, ProcessLookupError):
                    pass
            else:
                # Windows: Use start_new_session for isolation
                process = subprocess.Popen(
                    [self.config.python_executable, "-c", code],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=env,
                    cwd=work_dir,
                    start_new_session=True,
                    close_fds=True
                )
            
            # Wait with timeout
            try:
                stdout, stderr = process.communicate(timeout=timeout)
                return_code = process.returncode
                execution_time = time.time() - start_time
                # log the stdout and stderr
                logger.info(f"[{execution_id}] stdout: {stdout}")
                logger.info(f"[{execution_id}] stderr: {stderr}")
                logger.info(f"[{execution_id}] return_code: {return_code}")
                logger.info(f"[{execution_id}] execution_time: {execution_time}")
                # Try to get memory usage (approximate)
                
                return ExecutionResult(
                    stdout=stdout or "",
                    stderr=stderr or "",
                    return_code=return_code,
                    execution_time=execution_time,
                    timed_out=False
                )
                
            except subprocess.TimeoutExpired:
                logger.warning(f"[{execution_id}] Process timeout, terminating...")
                # Terminate process
                if process:
                    try:
                        if os.name != 'nt':
                            try:
                                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                            except (ProcessLookupError, OSError):
                                process.terminate()
                        else:
                            process.terminate()
                        
                        try:
                            process.wait(timeout=1)
                        except subprocess.TimeoutExpired:
                            if os.name != 'nt':
                                try:
                                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                                except (ProcessLookupError, OSError):
                                    process.kill()
                            else:
                                process.kill()
                            process.wait()
                    except Exception as e:
                        logger.error(f"[{execution_id}] Error terminating process: {e}")
                
                return ExecutionResult(
                    stdout="",
                    stderr=f"Execution timed out after {timeout} seconds",
                    return_code=-1,
                    execution_time=time.time() - start_time,
                    timed_out=True
                )
                
        except Exception as e:
            logger.error(f"[{execution_id}] Process execution error: {e}", exc_info=True)
            # Terminate process if it exists
            if process:
                try:
                    if os.name != 'nt':
                        try:
                            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                        except (ProcessLookupError, OSError):
                            process.terminate()
                    else:
                        process.terminate()
                    process.wait(timeout=1)
                except Exception:
                    if process:
                        try:
                            if os.name != 'nt':
                                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                            else:
                                process.kill()
                        except Exception:
                            pass
            
            return ExecutionResult(
                stdout="",
                stderr=f"Process execution failed: {str(e)}",
                return_code=-1,
                execution_time=time.time() - start_time,
                timed_out=False
            )
    
    async def shutdown(self):
        """Shutdown the execution service and cleanup resources."""
        logger.info("Shutting down execution service...")
        if self.active_executions:
            logger.info(f"Waiting for {len(self.active_executions)} active executions...")
            await asyncio.wait_for(
                asyncio.gather(*self.active_executions.values(), return_exceptions=True),
                timeout=30
            )
        logger.info("Execution service shut down complete")
