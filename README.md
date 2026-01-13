# Python Execution Agent

A minimal backend service that accepts Python code, executes it **safely in isolation**, and returns stdout/stderr. Built with FastAPI, demonstrating clean architecture, safety controls, and good API design.

## Features

- ✅ **Safe Isolation**: Code executes in separate OS processes (never in the FastAPI process)
- ✅ **Timeout Protection**: Configurable timeouts (1-30 seconds) with automatic process termination
- ✅ **Clean Architecture**: Separation of concerns with routes, services, models, and utils
- ✅ **Async Support**: FastAPI async endpoints for concurrent request handling
- ✅ **Comprehensive Logging**: Structured logging throughout the application
- ✅ **Type Safety**: Full type hints and Pydantic models
- ✅ **Error Handling**: Robust error handling with proper HTTP status codes

## Architecture

```
/app
   /routes      - API endpoints and routing
   /services    - Business logic (execution service)
   /models      - Pydantic models for requests/responses
   /utils        - Utility functions (process management)
main.py         - Application entry point
```

## Installation

1. Create and activate virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Running the Application

```bash
python main.py
```

The API will be available at `http://localhost:8000`

- API Documentation: `http://localhost:8000/docs`
- Alternative Docs: `http://localhost:8000/redoc`
- Health Check: `http://localhost:8000/health`

## API Usage

### Execute Python Code

**Endpoint:** `POST /api/v1/execute`

**Request Body:**
```json
{
  "code": "print('Hello, World!')\nresult = 2 + 2\nprint(f'Result: {result}')",
  "timeout": 5
}
```

**Response:**
```json
{
  "status": "success",
  "stdout": "Hello, World!\nResult: 4\n",
  "stderr": "",
  "execution_time": 0.05,
  "return_code": 0
}
```

**Status Values:**
- `success`: Code executed successfully
- `error`: Code execution failed with errors
- `timeout`: Execution exceeded the timeout limit
- `failed`: Execution failed for other reasons

## Safety Features

1. **Process Isolation**: Each code execution runs in a separate subprocess, preventing crashes from affecting the API server
2. **Timeout Protection**: Configurable timeouts with automatic process termination using SIGKILL
3. **Environment Isolation**: Isolated environment variables to prevent code from accessing sensitive data
4. **No In-Process Execution**: Code is never executed using `exec()` or `eval()` in the main process

## Example Requests

### Simple Calculation
```bash
curl -X POST "http://localhost:8000/api/v1/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "code": "x = 10\ny = 20\nprint(f\"Sum: {x + y}\")",
    "timeout": 5
  }'
```

### Error Handling
```bash
curl -X POST "http://localhost:8000/api/v1/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "code": "print(undefined_variable)",
    "timeout": 5
  }'
```

### Timeout Test
```bash
curl -X POST "http://localhost:8000/api/v1/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "code": "import time\ntime.sleep(10)",
    "timeout": 2
  }'
```

## Development

The project follows clean architecture principles:

- **Routes** (`app/routes/`): Handle HTTP requests/responses
- **Services** (`app/services/`): Contain business logic
- **Models** (`app/models/`): Define data structures with Pydantic
- **Utils** (`app/utils/`): Provide reusable utility functions

## License

MIT

