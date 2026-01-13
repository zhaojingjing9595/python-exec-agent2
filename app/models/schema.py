"""
Data models for general requests and responses.
"""
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class ExecutionStatus(str, Enum):
    """Execution status enumeration."""
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    FAILED = "failed"


class CodeExecutionRequest(BaseModel):
    """Request model for code execution."""
    code: str = Field(..., description="Python code to execute", min_length=1)
    timeout: Optional[int] = Field(
        default=5,
        description="Maximum execution time in seconds",
        ge=1,
        le=30
    )

    class Config:
        json_schema_extra = {
            "example": {
                "code": "print('Hello, World!')\nresult = 2 + 2\nprint(f'Result: {result}')",
                "timeout": 5
            }
        }


class CodeExecutionResponse(BaseModel):
    """Response model for code execution."""
    status: ExecutionStatus = Field(..., description="Execution status")
    stdout: str = Field(default="", description="Standard output")
    stderr: str = Field(default="", description="Standard error output")
    execution_time: float = Field(..., description="Execution time in seconds")
    return_code: Optional[int] = Field(default=None, description="Process return code")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "stdout": "Hello, World!\nResult: 4\n",
                "stderr": "",
                "execution_time": 0.05,
                "return_code": 0
            }
        }


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str = Field(default="healthy", description="Health status: 'healthy' or 'unhealthy'")
    timestamp: str = Field(..., description="Current timestamp")
    checks: Optional[dict] = Field(default=None, description="Detailed health check results")
