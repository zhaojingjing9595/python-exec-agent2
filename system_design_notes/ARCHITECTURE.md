# Execution Engine Architecture

## Overview

The Python Execution Agent uses a **three-layer architecture** that completely separates the API layer from code execution, ensuring maximum safety and isolation.

## Architecture Layers

### 1. API Layer (`app/routes/`)
- **Purpose**: Handle HTTP requests/responses
- **Responsibilities**:
  - Request validation
  - Response formatting
  - Error handling at API level
- **Files**: `route_execution.py`, `route_general.py`

### 2. Service Layer (`app/services/`)
- **Purpose**: Business logic and orchestration
- **Responsibilities**:
  - Bridge between API and execution engine
  - Convert between API models and engine types
  - Manage execution lifecycle
- **Files**: `execution_service.py`

### 3. Execution Engine (`app/services/execution_engine.py`)
- **Purpose**: Core execution with full isolation
- **Responsibilities**:
  - Async code execution
  - Process isolation
  - Resource limits enforcement
  - Timeout management
  - Concurrent execution control

## Key Safety Features

### Process Isolation
- **Separate OS Processes**: Each code execution runs in a completely separate subprocess
- **No In-Process Execution**: Code is NEVER executed using `exec()` or `eval()` in the main process
- **Process Groups**: On Unix, processes run in separate process groups for better signal handling

### Resource Limits
- **Memory Limits**: Configurable memory limits per execution (default: 128MB)
- **CPU Time Limits**: Maximum CPU time per execution (default: 10 seconds)
- **File Descriptor Limits**: Limited to prevent resource exhaustion
- **Implementation**: Uses `resource.setrlimit()` on Unix systems

### Timeout Protection
- **Configurable Timeouts**: 1-30 seconds per execution
- **Automatic Termination**: Processes are forcefully killed if they exceed timeout
- **Graceful Shutdown**: SIGTERM first, then SIGKILL if needed
- **Process Tree Termination**: All child processes are terminated

### Filesystem Isolation
- **Temporary Directories**: Each execution gets its own isolated temporary directory
- **Automatic Cleanup**: Directories are cleaned up after execution
- **No Host Access**: Code cannot access host filesystem outside its isolated directory

### Concurrency Control
- **Semaphore-Based**: Limits concurrent executions (default: 10)
- **Async/Await**: Fully async to prevent blocking
- **Non-Blocking**: Uses `run_in_executor` to avoid blocking the event loop
- **Parallel Execution**: Multiple requests can execute simultaneously

## Execution Flow

```
1. API Request → route_execution.py
   ↓
2. ExecutionService.execute_code()
   ↓
3. ExecutionEngine.execute()
   ↓
4. _execute_isolated() - Creates isolated environment
   ↓
5. _run_with_limits() - Runs in executor with resource limits
   ↓
6. Subprocess execution with timeout
   ↓
7. Result collection and cleanup
   ↓
8. Response returned to API
```

## Configuration

The execution engine can be configured via `ExecutionConfig`:

```python
ExecutionConfig(
    timeout=5,                          # Default timeout in seconds
    max_memory_mb=128,                 # Memory limit per execution
    max_cpu_time=10,                   # CPU time limit
    python_executable="python3",        # Python interpreter
    enable_filesystem_isolation=True,  # Enable temp directory isolation
    max_concurrent_executions=10       # Max parallel executions
)
```

## Error Handling

### Timeout Handling
- Process is terminated with SIGTERM
- If not terminated within 1 second, SIGKILL is sent
- All child processes are terminated
- Returns `TIMEOUT` status

### Memory Limit Exceeded
- Process is killed by OS (SIGKILL)
- Returns `FAILED` status with appropriate error message

### Process Crashes
- Crashes are isolated to the subprocess
- API layer remains unaffected
- Returns `ERROR` status with stderr output

### Resource Exhaustion
- Semaphore prevents too many concurrent executions
- Returns appropriate error if limit is reached

## Platform Support

### Unix (Linux, macOS)
- Full resource limits support
- Process group management
- Signal-based termination
- Memory usage tracking via `/proc`

### Windows
- Basic process isolation
- No resource limits (OS limitation)
- Process termination via `terminate()`/`kill()`
- Limited memory tracking

## Performance Considerations

- **Async Execution**: Non-blocking, allows concurrent requests
- **Process Pool**: Each execution is independent, no shared state
- **Resource Limits**: Prevents resource exhaustion
- **Cleanup**: Automatic cleanup prevents disk space issues
- **Semaphore**: Prevents overwhelming the system

## Security Considerations

1. **No Code Injection**: Code is passed as string to subprocess, not executed in main process
2. **Isolated Environment**: Each execution has its own environment
3. **Resource Limits**: Prevents DoS attacks via resource exhaustion
4. **Timeout Protection**: Prevents infinite loops
5. **Filesystem Isolation**: Prevents access to host filesystem
6. **Process Isolation**: Crashes don't affect the API server

## Future Enhancements

- Container-based isolation (Docker)
- Network isolation
- More granular resource limits
- Execution history/audit logging
- Rate limiting per client
- Sandboxed Python interpreter

