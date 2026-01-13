# Queue-Based Code Execution Implementation Guide

## Overview

Moving code execution to a queue system decouples HTTP requests from actual execution, providing:
- **Better scalability**: Workers can scale independently
- **Non-blocking requests**: API returns immediately with job ID
- **Retry mechanisms**: Failed executions can be retried
- **Job tracking**: Monitor execution status
- **Resource isolation**: Workers can be separate processes/servers

## Architecture Options

### Option 1: Redis Queue (RQ) - **Simplest** ✅ Recommended for Start

**Pros:**
- Very simple to set up
- Redis-based (lightweight)
- Good for Python
- Easy debugging

**Cons:**
- Redis only (no RabbitMQ)
- Simpler feature set than Celery

**Implementation:**

```python
# requirements.txt addition
rq==1.15.1
redis==5.0.1

# New file: app/workers/execution_worker.py
from rq import Job
from app.services.execution_service import ExecutionService
from app.models.schema import CodeExecutionRequest, CodeExecutionResponse

execution_service = ExecutionService()

def execute_code_task(request_dict: dict) -> dict:
    """RQ task function - must be picklable, no async."""
    request = CodeExecutionRequest(**request_dict)
    # RQ doesn't support async, so we need sync wrapper
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(
            execution_service.execute_code(request)
        )
        return result.dict()
    finally:
        loop.close()

# Modified route: app/routes/route_execution.py
from rq import Queue
from redis import Redis

redis_conn = Redis()
q = Queue('code_execution', connection=redis_conn)

@router.post("/execute", response_model=JobResponse)
async def execute_code(request: CodeExecutionRequest) -> JobResponse:
    """Queue code execution and return job ID."""
    job = q.enqueue(
        'app.workers.execution_worker.execute_code_task',
        request.dict(),
        job_timeout=request.timeout + 10  # Buffer for cleanup
    )
    return JobResponse(job_id=job.id, status="queued")

@router.get("/execute/{job_id}", response_model=CodeExecutionResponse)
async def get_execution_result(job_id: str):
    """Get execution result by job ID."""
    job = Job.fetch(job_id, connection=redis_conn)
    if job.is_finished:
        return CodeExecutionResponse(**job.result)
    elif job.is_failed:
        return CodeExecutionResponse(
            status=ExecutionStatus.FAILED,
            stderr=str(job.exc_info),
            execution_time=0.0
        )
    else:
        return {"status": job.get_status()}  # pending/started
```

---

### Option 2: Celery - **Most Feature-Rich** ✅ Recommended for Production

**Pros:**
- Industry standard
- Supports Redis, RabbitMQ, databases
- Rich features (retries, chains, groups, etc.)
- Monitoring tools (Flower)
- Better for complex workflows

**Cons:**
- More complex setup
- Requires broker + result backend

**Implementation:**

```python
# requirements.txt addition
celery==5.3.4
redis==5.0.1  # or kombu for RabbitMQ

# New file: app/celery_app.py
from celery import Celery

celery_app = Celery(
    'code_executor',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0'
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_time_limit=60,  # Hard limit
    task_soft_time_limit=30,  # Soft limit
)

# New file: app/tasks/execution_tasks.py
from app.celery_app import celery_app
from app.services.execution_service import ExecutionService
from app.models.schema import CodeExecutionRequest
import asyncio

execution_service = ExecutionService()

@celery_app.task(
    bind=True,
    name='execute_code',
    max_retries=0,  # Don't retry code execution
    time_limit=60,
    soft_time_limit=30
)
def execute_code_task(self, request_dict: dict):
    """Celery task - wraps async execution service."""
    request = CodeExecutionRequest(**request_dict)
    
    # Celery doesn't natively support async, but we can work around it
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(
            execution_service.execute_code(request)
        )
        return result.dict()
    except Exception as exc:
        # Task will be marked as failed
        raise self.retry(exc=exc, countdown=0)  # Don't retry, just fail
    finally:
        loop.close()

# Modified route: app/routes/route_execution.py
from app.tasks.execution_tasks import execute_code_task

@router.post("/execute", response_model=JobResponse)
async def execute_code(request: CodeExecutionRequest) -> JobResponse:
    """Queue code execution and return job ID."""
    task = execute_code_task.delay(request.dict())
    return JobResponse(job_id=task.id, status="queued")

@router.get("/execute/{job_id}", response_model=CodeExecutionResponse)
async def get_execution_result(job_id: str):
    """Get execution result by job ID."""
    from app.celery_app import celery_app
    task_result = celery_app.AsyncResult(job_id)
    
    if task_result.ready():
        if task_result.successful():
            return CodeExecutionResponse(**task_result.result)
        else:
            return CodeExecutionResponse(
                status=ExecutionStatus.FAILED,
                stderr=str(task_result.info),
                execution_time=0.0
            )
    else:
        return {"status": task_result.state}  # PENDING, STARTED, etc.
```

---

### Option 3: RabbitMQ (Direct) - **Most Control**

**Pros:**
- Full control over message routing
- Advanced messaging patterns
- Language agnostic

**Cons:**
- More low-level implementation
- More boilerplate
- Usually better to use Celery on top

**Not recommended** unless you need specific RabbitMQ features.

---

### Option 4: FastAPI BackgroundTasks - **Simplest but Limited**

**Pros:**
- Built into FastAPI
- No external dependencies
- Simple for async tasks

**Cons:**
- **Not suitable for subprocess execution!**
- Runs in same process (blocks if you use subprocess)
- No job tracking
- No retries
- Lost on server restart

**Not recommended** for your use case.

---

## Recommended Approach: Celery with Redis

### Implementation Steps

#### 1. Install Dependencies

```bash
pip install celery redis
```

#### 2. Update Models

```python
# app/models/schema.py - Add new models

class JobResponse(BaseModel):
    """Response when job is queued."""
    job_id: str = Field(..., description="Job ID for tracking")
    status: str = Field(default="queued", description="Initial job status")
    message: str = Field(default="Execution queued", description="Status message")

class JobStatus(str, Enum):
    """Job status enumeration."""
    PENDING = "pending"
    QUEUED = "queued"
    STARTED = "started"
    SUCCESS = "success"
    FAILURE = "failure"
    RETRY = "retry"
    REVOKED = "revoked"
```

#### 3. Create Celery App

```python
# app/celery_app.py
from celery import Celery
import os

celery_app = Celery(
    'code_executor',
    broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_time_limit=60,  # Hard limit for entire task
    task_soft_time_limit=35,  # Soft limit (raises SoftTimeLimitExceeded)
    worker_prefetch_multiplier=1,  # Process one task at a time
    task_acks_late=True,  # Ack after task completes
    worker_max_tasks_per_child=50,  # Restart worker after 50 tasks (memory leak prevention)
)
```

#### 4. Create Task Wrapper

```python
# app/tasks/execution_tasks.py
from app.celery_app import celery_app
from app.services.execution_service import ExecutionService
from app.models.schema import CodeExecutionRequest
import asyncio
import logging

logger = logging.getLogger(__name__)
execution_service = ExecutionService()

@celery_app.task(
    bind=True,
    name='execute_code',
    max_retries=0,  # Don't auto-retry code execution
    time_limit=60,
    soft_time_limit=35
)
def execute_code_task(self, request_dict: dict):
    """
    Celery task wrapper for code execution.
    
    Note: Celery tasks must be sync functions, but we can call async code.
    """
    request = CodeExecutionRequest(**request_dict)
    execution_id = request_dict.get('execution_id', self.request.id[:8])
    
    logger.info(f"[{execution_id}] Task queued for execution")
    
    # Create new event loop for this task
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Execute code (this includes subprocess timeout handling)
        result = loop.run_until_complete(
            execution_service.execute_code(request)
        )
        
        logger.info(f"[{execution_id}] Task completed: {result.status}")
        return result.dict()
        
    except asyncio.TimeoutError:
        logger.error(f"[{execution_id}] Task timed out")
        return {
            "status": "timeout",
            "stdout": "",
            "stderr": "Task execution timed out",
            "execution_time": request.timeout,
            "return_code": None
        }
    except Exception as exc:
        logger.error(f"[{execution_id}] Task failed: {exc}", exc_info=True)
        # Re-raise so Celery marks task as failed
        raise
    finally:
        loop.close()
```

#### 5. Update Routes

```python
# app/routes/route_execution.py
from fastapi import APIRouter, HTTPException, status
from app.models.schema import (
    CodeExecutionRequest, 
    CodeExecutionResponse, 
    JobResponse,
    ExecutionStatus
)
from app.tasks.execution_tasks import execute_code_task
from app.celery_app import celery_app
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["execution"])

@router.post(
    "/execute",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,  # 202 = Accepted (queued)
    summary="Queue Python code execution",
    description="Queue Python code for execution. Returns job ID to track status."
)
async def execute_code(request: CodeExecutionRequest) -> JobResponse:
    """Queue code execution and return job ID."""
    try:
        task = execute_code_task.delay(request.dict())
        logger.info(f"Queued execution task: {task.id}")
        return JobResponse(
            job_id=task.id,
            status="queued",
            message=f"Code execution queued. Use job_id {task.id} to check status."
        )
    except Exception as e:
        logger.error(f"Failed to queue execution: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue execution: {str(e)}"
        )

@router.get(
    "/execute/{job_id}",
    response_model=CodeExecutionResponse,
    summary="Get execution result",
    description="Get the result of a code execution by job ID."
)
async def get_execution_result(job_id: str):
    """Get execution result by job ID."""
    try:
        task_result = celery_app.AsyncResult(job_id)
        
        if task_result.ready():
            if task_result.successful():
                # Task completed successfully
                result_dict = task_result.result
                return CodeExecutionResponse(**result_dict)
            else:
                # Task failed
                error_info = task_result.info
                logger.error(f"Task {job_id} failed: {error_info}")
                return CodeExecutionResponse(
                    status=ExecutionStatus.FAILED,
                    stdout="",
                    stderr=str(error_info) if error_info else "Task execution failed",
                    execution_time=0.0,
                    return_code=None
                )
        else:
            # Task still running
            raise HTTPException(
                status_code=status.HTTP_202_ACCEPTED,
                detail={
                    "status": task_result.state,
                    "job_id": job_id,
                    "message": f"Execution {task_result.state}. Check again later."
                }
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting task result: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get execution result: {str(e)}"
        )
```

#### 6. Run Celery Worker

```bash
# Terminal 1: Start FastAPI
python main.py

# Terminal 2: Start Celery Worker
celery -A app.celery_app worker --loglevel=info --concurrency=4

# Optional: Terminal 3: Start Celery Flower (monitoring)
celery -A app.celery_app flower
```

---

## Important Considerations

### 1. **Subprocess Timeout in Queue**

The subprocess timeout (`request.timeout`) is still enforced within the Celery task. Additionally:
- **Celery `time_limit`**: Hard limit (kills worker if exceeded)
- **Celery `soft_time_limit`**: Soft limit (raises exception, allows cleanup)
- **Subprocess `timeout`**: User-specified limit for code execution

**Recommendation**: Set Celery limits higher than subprocess timeout:
```python
task_time_limit = request.timeout + 10  # 10s buffer for cleanup
```

### 2. **Process Killing in Workers**

The existing process group killing logic in `_run_subprocess` will still work in Celery workers. However, you should also handle Celery's timeout:

```python
from celery.exceptions import SoftTimeLimitExceeded

@celery_app.task(bind=True)
def execute_code_task(self, request_dict: dict):
    try:
        # ... execution code ...
    except SoftTimeLimitExceeded:
        # Celery soft timeout - subprocess should already be killed
        logger.warning("Celery soft time limit exceeded")
        return {"status": "timeout", ...}
```

### 3. **Resource Limits per Worker**

Each Celery worker should respect the semaphore limits. Options:
- **One worker per execution**: `--concurrency=1` per worker
- **Shared semaphore**: Use Redis-based semaphore across workers
- **Per-worker limits**: Each worker has its own `ExecutionService` with semaphore

### 4. **Result Storage**

Celery needs a result backend (Redis recommended). Results expire after 24h by default. Adjust:
```python
celery_app.conf.result_expires = 3600  # 1 hour
```

### 5. **Worker Scaling**

Workers can scale independently:
```bash
# Run 4 workers on machine 1
celery -A app.celery_app worker --concurrency=4

# Run 4 workers on machine 2
celery -A app.celery_app worker --concurrency=4
```

Total capacity = `num_workers × concurrency × semaphore_limit`

---

## Comparison Matrix

| Feature | RQ | Celery | RabbitMQ Direct | BackgroundTasks |
|---------|----|---------|-----------------|-----------------|
| Setup Complexity | ⭐ Simple | ⭐⭐ Medium | ⭐⭐⭐ Complex | ⭐ Simple |
| Features | Basic | Rich | Full Control | Limited |
| Monitoring | Basic | Flower | Custom | None |
| Retries | ✅ | ✅ | Custom | ❌ |
| Job Tracking | ✅ | ✅ | Custom | ❌ |
| Scaling | ✅ | ✅ | ✅ | ❌ |
| Production Ready | ⚠️ Small scale | ✅ Yes | ✅ Yes | ❌ No |

---

## Recommendation

**For your use case (code execution with subprocess isolation):**

1. **Start with RQ** if you want something simple and quick
2. **Use Celery** if you need production-grade features, monitoring, and scaling
3. **Both** will work with your existing `ExecutionService` with minimal changes

The subprocess sandboxing, resource limits, and timeout handling will all work the same way - they just run in worker processes instead of the API process.

