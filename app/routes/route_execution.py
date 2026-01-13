"""
Routes for code execution endpoints.
"""
from fastapi import APIRouter, HTTPException, status
from app.models.schema import CodeExecutionRequest, CodeExecutionResponse
from app.services.execution_service import ExecutionService
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["execution"])

# Initialize execution service
execution_service = ExecutionService()


@router.post(
    "/execute",
    response_model=CodeExecutionResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute Python code",
    description="Execute Python code safely in an isolated subprocess with timeout protection."
)
async def execute_code(request: CodeExecutionRequest) -> CodeExecutionResponse:
    """
    Execute Python code in a safe, isolated environment.
    
    - **code**: Python code to execute
    - **timeout**: Maximum execution time in seconds (1-30, default: 5)
    
    Returns execution results including stdout, stderr, and execution time.
    """
    try:
        logger.info(f"Received execution request with timeout: {request.timeout}s")
        response = await execution_service.execute_code(request)
        return response
    except Exception as e:
        logger.error(f"Error in execute_code endpoint::{type(e).__name__}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute code: {str(e)}"
        )

