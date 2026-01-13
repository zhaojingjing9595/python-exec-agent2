"""
General routes for health checks and root endpoint.
"""
import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from fastapi import APIRouter

from app.models.schema import HealthResponse

router = APIRouter(tags=["general"])


@router.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Python Execution Agent API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@router.get("/health")
async def health():
    """
    Health check endpoint that verifies critical system dependencies.
    
    Checks:
    - Python executable availability
    - Subprocess creation capability
    - Temporary directory creation (for sandbox)
    - Basic system resources
    """
    checks = {}
    all_healthy = True
    
    # Check 1: Python executable availability
    python_executable = shutil.which("python3")
    if python_executable:
        checks["python_executable"] = {
            "status": "ok",
            "path": python_executable
        }
        # Verify Python can actually run
        try:
            result = subprocess.run(
                [python_executable, "--version"],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                checks["python_executable"]["version"] = result.stdout.strip()
            else:
                checks["python_executable"]["status"] = "error"
                checks["python_executable"]["error"] = "Python executable failed to run"
                all_healthy = False
        except subprocess.TimeoutExpired:
            checks["python_executable"]["status"] = "error"
            checks["python_executable"]["error"] = "Python executable timeout"
            all_healthy = False
        except Exception as e:
            checks["python_executable"]["status"] = "error"
            checks["python_executable"]["error"] = str(e)
            all_healthy = False
    else:
        checks["python_executable"] = {
            "status": "error",
            "error": "Python3 executable not found in PATH"
        }
        all_healthy = False
    
    # Check 2: Subprocess creation capability (critical for execution)
    if python_executable:
        try:
            test_process = subprocess.run(
                [python_executable, "-c", "print('ok')"],
                capture_output=True,
                text=True,
                timeout=2
            )
            if test_process.returncode == 0:
                checks["subprocess_creation"] = {
                    "status": "ok",
                    "message": "Can create and execute subprocesses"
                }
            else:
                checks["subprocess_creation"] = {
                    "status": "error",
                    "error": f"Subprocess returned non-zero code: {test_process.returncode}"
                }
                all_healthy = False
        except subprocess.TimeoutExpired:
            checks["subprocess_creation"] = {
                "status": "error",
                "error": "Subprocess creation timeout"
            }
            all_healthy = False
        except Exception as e:
            checks["subprocess_creation"] = {
                "status": "error",
                "error": f"Cannot create subprocesses: {str(e)}"
            }
            all_healthy = False
    else:
        checks["subprocess_creation"] = {
            "status": "error",
            "error": "Cannot test subprocess creation: Python executable not found"
        }
        all_healthy = False
    
    # Check 3: Temporary directory creation (for sandbox)
    try:
        test_dir = tempfile.mkdtemp(prefix="health_check_")
        if os.path.exists(test_dir):
            checks["temp_directory"] = {
                "status": "ok",
                "message": "Can create temporary directories"
            }
            # Cleanup
            shutil.rmtree(test_dir, ignore_errors=True)
        else:
            checks["temp_directory"] = {
                "status": "error",
                "error": "Temporary directory was not created"
            }
            all_healthy = False
    except Exception as e:
        checks["temp_directory"] = {
            "status": "error",
            "error": f"Cannot create temporary directories: {str(e)}"
        }
        all_healthy = False
    
    # Check 4: Disk space (basic check - ensure temp directory is writable)
    try:
        temp_dir = tempfile.gettempdir()
        stat = os.statvfs(temp_dir) if hasattr(os, 'statvfs') else None
        if stat:
            free_space_gb = (stat.f_bavail * stat.f_frsize) / (1024 ** 3)
            checks["disk_space"] = {
                "status": "ok" if free_space_gb > 0.1 else "warning",
                "free_space_gb": round(free_space_gb, 2),
                "message": f"Available disk space in temp directory: {free_space_gb:.2f} GB"
            }
            if free_space_gb < 0.1:
                all_healthy = False
        else:
            # Windows or system without statvfs - just check if we can write
            test_file = os.path.join(temp_dir, "health_check_test")
            try:
                with open(test_file, "w") as f:
                    f.write("test")
                os.remove(test_file)
                checks["disk_space"] = {
                    "status": "ok",
                    "message": "Temp directory is writable"
                }
            except Exception as e:
                checks["disk_space"] = {
                    "status": "error",
                    "error": f"Cannot write to temp directory: {str(e)}"
                }
                all_healthy = False
    except Exception as e:
        checks["disk_space"] = {
            "status": "warning",
            "error": f"Could not check disk space: {str(e)}"
        }
    
    status = "healthy" if all_healthy else "unhealthy"
    
    return HealthResponse(
        status=status,
        timestamp=datetime.now().isoformat(),
        checks=checks
    )

