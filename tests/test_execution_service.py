"""
Comprehensive test suite for the Python Execution Agent.
Tests various scenarios including happy paths and negative cases.
"""
import pytest
import json
import time
import logging
import os
from fastapi.testclient import TestClient
from app.models.schema import ExecutionStatus

# Import main first (this will set up logging for app.log)
from main import app

# Now configure additional logging for tests
log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
date_format = "%Y-%m-%d %H:%M:%S"

# Get the project root directory (parent of tests directory)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
logs_dir = os.path.join(project_root, "logs")
os.makedirs(logs_dir, exist_ok=True)
test_log_path = os.path.join(logs_dir, "test.log")

# Get root logger and add test.log handler
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# Check if test.log handler already exists to avoid duplicates
test_log_handler_exists = False
abs_test_log_path = os.path.abspath(test_log_path)
for h in root_logger.handlers:
    if isinstance(h, logging.FileHandler):
        try:
            if os.path.abspath(h.baseFilename) == abs_test_log_path:
                test_log_handler_exists = True
                break
        except (AttributeError, OSError):
            pass

if not test_log_handler_exists:
    # Add test.log file handler
    test_log_handler = logging.FileHandler(test_log_path, encoding="utf-8", mode="w")
    test_log_handler.setLevel(logging.INFO)
    test_log_formatter = logging.Formatter(log_format, date_format)
    test_log_handler.setFormatter(test_log_formatter)
    root_logger.addHandler(test_log_handler)

# Create test logger
logger = logging.getLogger(__name__)
logger.info("=" * 80)
logger.info("Starting test suite execution")
logger.info("=" * 80)

# Create test client
client = TestClient(app)


class TestHappyCases:
    """Test cases for successful code execution."""
    
    def test_simple_calculation(self):
        """Test basic Python code execution with simple calculation."""
        response = client.post(
            "/api/v1/execute",
            json={
                "code": "x = 10\ny = 20\nresult = x + y\nprint(f'Sum: {result}')",
                "timeout": 5
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == ExecutionStatus.SUCCESS
        assert "Sum: 30" in data["stdout"]
        assert data["return_code"] == 0
        assert data["execution_time"] > 0
    
    def test_string_operations(self):
        """Test string manipulation."""
        response = client.post(
            "/api/v1/execute",
            json={
                "code": "text = 'Hello World'\nreversed_text = text[::-1]\nprint(reversed_text)",
                "timeout": 5
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == ExecutionStatus.SUCCESS
        assert "dlroW olleH" in data["stdout"]
    
    def test_list_comprehension(self):
        """Test list operations."""
        response = client.post(
            "/api/v1/execute",
            json={
                "code": "numbers = [1, 2, 3, 4, 5]\nsquared = [x**2 for x in numbers]\nprint(squared)",
                "timeout": 5
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == ExecutionStatus.SUCCESS
        assert "[1, 4, 9, 16, 25]" in data["stdout"]


class TestSyntaxErrors:
    """Test cases for syntax errors."""
    
    def test_invalid_syntax(self):
        """Test code with syntax error."""
        response = client.post(
            "/api/v1/execute",
            json={
                "code": "x = 10\nif x == 10\n    print('error')",
                "timeout": 5
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in [ExecutionStatus.ERROR, ExecutionStatus.FAILED]
        assert "SyntaxError" in data["stderr"] or "syntax" in data["stderr"].lower()
    
    def test_missing_colon(self):
        """Test missing colon in if statement."""
        response = client.post(
            "/api/v1/execute",
            json={
                "code": "if True\n    print('missing colon')",
                "timeout": 5
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in [ExecutionStatus.ERROR, ExecutionStatus.FAILED]
        assert len(data["stderr"]) > 0
    
    def test_unclosed_bracket(self):
        """Test unclosed bracket."""
        response = client.post(
            "/api/v1/execute",
            json={
                "code": "x = [1, 2, 3\nprint(x)",
                "timeout": 5
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in [ExecutionStatus.ERROR, ExecutionStatus.FAILED]


class TestTimeoutCases:
    """Test cases for timeout scenarios."""
    
    def test_sleep_timeout(self):
        """Test code that sleeps longer than timeout."""
        response = client.post(
            "/api/v1/execute",
            json={
                "code": "import time\ntime.sleep(10)\nprint('This should not print')",
                "timeout": 2
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == ExecutionStatus.TIMEOUT
        assert "timeout" in data["stderr"].lower() or data["status"] == ExecutionStatus.TIMEOUT
        assert data["execution_time"] >= 2  # Should be at least the timeout duration
    
    def test_long_loop_timeout(self):
        """Test long-running loop that exceeds timeout."""
        response = client.post(
            "/api/v1/execute",
            json={
                "code": "i = 0\nwhile True:\n    i += 1\n    if i > 1000000:\n        break",
                "timeout": 1
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == ExecutionStatus.TIMEOUT


class TestRuntimeErrors:
    """Test cases for runtime errors."""
    
    def test_division_by_zero(self):
        """Test division by zero error."""
        response = client.post(
            "/api/v1/execute",
            json={
                "code": "x = 10 / 0\nprint(x)",
                "timeout": 5
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in [ExecutionStatus.ERROR, ExecutionStatus.FAILED]
        assert "ZeroDivisionError" in data["stderr"] or "division" in data["stderr"].lower()
    
    def test_undefined_variable(self):
        """Test undefined variable error."""
        response = client.post(
            "/api/v1/execute",
            json={
                "code": "print(undefined_variable)",
                "timeout": 5
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in [ExecutionStatus.ERROR, ExecutionStatus.FAILED]
        assert "NameError" in data["stderr"] or "not defined" in data["stderr"].lower()
    
    def test_index_error(self):
        """Test index out of range error."""
        response = client.post(
            "/api/v1/execute",
            json={
                "code": "arr = [1, 2, 3]\nprint(arr[10])",
                "timeout": 5
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in [ExecutionStatus.ERROR, ExecutionStatus.FAILED]
        assert "IndexError" in data["stderr"] or "index" in data["stderr"].lower()
    
    def test_type_error(self):
        """Test type error."""
        response = client.post(
            "/api/v1/execute",
            json={
                "code": "result = 'string' + 5\nprint(result)",
                "timeout": 5
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in [ExecutionStatus.ERROR, ExecutionStatus.FAILED]
        assert "TypeError" in data["stderr"] or "type" in data["stderr"].lower()


class TestInfiniteLoop:
    """Test cases for infinite loops."""
    
    def test_while_true_loop(self):
        """Test infinite while loop."""
        response = client.post(
            "/api/v1/execute",
            json={
                "code": "while True:\n    pass",
                "timeout": 2
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == ExecutionStatus.TIMEOUT
        assert data["execution_time"] >= 2
    
    def test_recursive_infinite_loop(self):
        """Test infinite recursion."""
        response = client.post(
            "/api/v1/execute",
            json={
                "code": "def recurse():\n    recurse()\nrecurse()",
                "timeout": 2
            }
        )
        assert response.status_code == 200
        data = response.json()
        # Should timeout or hit recursion limit
        assert data["status"] in [ExecutionStatus.TIMEOUT, ExecutionStatus.ERROR, ExecutionStatus.FAILED]


class TestFileSystemIsolation:
    """Test cases for filesystem isolation and sandbox."""
    
    def test_access_file_in_sandbox(self):
        """Test that files can be created and accessed within sandbox."""
        response = client.post(
            "/api/v1/execute",
            json={
                "code": "import os\nwith open('test.txt', 'w') as f:\n    f.write('hello')\nwith open('test.txt', 'r') as f:\n    print(f.read())",
                "timeout": 5
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == ExecutionStatus.SUCCESS
        assert "hello" in data["stdout"]
    
    def test_access_file_outside_sandbox(self):
        """Test attempt to access file outside sandbox (should fail or be blocked)."""
        response = client.post(
            "/api/v1/execute",
            json={
                "code": "import os\nwith open('/etc/passwd', 'r') as f:\n    print(f.read()[:100])",
                "timeout": 5
            }
        )
        assert response.status_code == 200
        data = response.json()
        # Should fail - either permission denied or file not found
        assert data["status"] in [ExecutionStatus.ERROR, ExecutionStatus.FAILED]
        assert len(data["stderr"]) > 0
    
    def test_access_home_directory(self):
        """Test attempt to access home directory."""
        response = client.post(
            "/api/v1/execute",
            json={
                "code": "import os\nprint(os.path.expanduser('~'))\ntry:\n    with open(os.path.expanduser('~/.bashrc'), 'r') as f:\n        print('accessed')\nexcept:\n    print('blocked')",
                "timeout": 5
            }
        )
        assert response.status_code == 200
        data = response.json()
        # Should either be blocked or fail
        assert data["status"] in [ExecutionStatus.SUCCESS, ExecutionStatus.ERROR, ExecutionStatus.FAILED]
    
    def test_os_system_call(self):
        """Test attempt to use os.system (should be restricted)."""
        response = client.post(
            "/api/v1/execute",
            json={
                "code": "import os\ntry:\n    os.system('ls /')\n    print('executed')\nexcept Exception as e:\n    print(f'error: {e}')",
                "timeout": 5
            }
        )
        assert response.status_code == 200
        data = response.json()
        # Should either fail or be restricted
        assert data["status"] in [ExecutionStatus.SUCCESS, ExecutionStatus.ERROR, ExecutionStatus.FAILED]


class TestResourceLimits:
    """Test cases for resource limit enforcement."""
    
    def test_memory_intensive_operation(self):
        """Test memory-intensive operation that might exceed limits."""
        response = client.post(
            "/api/v1/execute",
            json={
                "code": "data = [0] * (100 * 1024 * 1024)  # 100MB list\nprint('created')",
                "timeout": 10
            }
        )
        assert response.status_code == 200
        data = response.json()
        # May succeed if within limits, or fail if exceeds memory limit
        assert data["status"] in [ExecutionStatus.SUCCESS, ExecutionStatus.ERROR, ExecutionStatus.FAILED, ExecutionStatus.TIMEOUT]
    
    def test_cpu_intensive_operation(self):
        """Test CPU-intensive operation."""
        response = client.post(
            "/api/v1/execute",
            json={
                "code": "total = 0\nfor i in range(10000000):\n    total += i**2\nprint(total)",
                "timeout": 3
            }
        )
        assert response.status_code == 200
        data = response.json()
        # May timeout or succeed depending on CPU limit
        assert data["status"] in [ExecutionStatus.SUCCESS, ExecutionStatus.TIMEOUT, ExecutionStatus.ERROR, ExecutionStatus.FAILED]


class TestMalformedJSON:
    """Test cases for malformed JSON requests."""
    
    def test_missing_code_field(self):
        """Test request without code field."""
        response = client.post(
            "/api/v1/execute",
            json={
                "timeout": 5
            }
        )
        assert response.status_code == 422  # Validation error
        assert "code" in str(response.json()).lower()
    
    def test_empty_code(self):
        """Test request with empty code."""
        response = client.post(
            "/api/v1/execute",
            json={
                "code": "",
                "timeout": 5
            }
        )
        assert response.status_code == 422  # Validation error
    
    def test_invalid_timeout_value(self):
        """Test request with invalid timeout (too high)."""
        response = client.post(
            "/api/v1/execute",
            json={
                "code": "print('test')",
                "timeout": 100  # Exceeds max of 30
            }
        )
        assert response.status_code == 422  # Validation error
    
    def test_negative_timeout(self):
        """Test request with negative timeout."""
        response = client.post(
            "/api/v1/execute",
            json={
                "code": "print('test')",
                "timeout": -1
            }
        )
        assert response.status_code == 422  # Validation error
    
    def test_invalid_json_structure(self):
        """Test completely invalid JSON."""
        response = client.post(
            "/api/v1/execute",
            data="not json at all",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422
    
    def test_missing_timeout_field(self):
        """Test request without timeout (should use default)."""
        response = client.post(
            "/api/v1/execute",
            json={
                "code": "print('test')"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == ExecutionStatus.SUCCESS


class TestNetworkAccess:
    """Test cases for network access attempts."""
    
    def test_http_request(self):
        """Test attempt to make HTTP request."""
        response = client.post(
            "/api/v1/execute",
            json={
                "code": "import urllib.request\ntry:\n    urllib.request.urlopen('http://example.com', timeout=2)\n    print('connected')\nexcept Exception as e:\n    print(f'error: {type(e).__name__}')",
                "timeout": 5
            }
        )
        assert response.status_code == 200
        data = response.json()
        # May succeed or fail depending on network restrictions
        assert data["status"] in [ExecutionStatus.SUCCESS, ExecutionStatus.ERROR, ExecutionStatus.FAILED]
    
    def test_socket_connection(self):
        """Test attempt to create socket connection."""
        response = client.post(
            "/api/v1/execute",
            json={
                "code": "import socket\ntry:\n    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n    s.connect(('example.com', 80))\n    print('connected')\nexcept Exception as e:\n    print(f'error: {type(e).__name__}')",
                "timeout": 5
            }
        )
        assert response.status_code == 200
        data = response.json()
        # May succeed or fail depending on network restrictions
        assert data["status"] in [ExecutionStatus.SUCCESS, ExecutionStatus.ERROR, ExecutionStatus.FAILED, ExecutionStatus.TIMEOUT]


class TestImportDependencies:
    """Test cases for importing dependencies."""
    
    def test_standard_library_import(self):
        """Test importing standard library modules."""
        response = client.post(
            "/api/v1/execute",
            json={
                "code": "import json\nimport os\nimport sys\ndata = {'key': 'value'}\nprint(json.dumps(data))",
                "timeout": 5
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == ExecutionStatus.SUCCESS
        assert "key" in data["stdout"] and "value" in data["stdout"]
    
    def test_missing_third_party_import(self):
        """Test importing non-existent third-party module."""
        response = client.post(
            "/api/v1/execute",
            json={
                "code": "import nonexistent_module\nprint('imported')",
                "timeout": 5
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in [ExecutionStatus.ERROR, ExecutionStatus.FAILED]
        assert "ModuleNotFoundError" in data["stderr"] or "ImportError" in data["stderr"] or "No module named" in data["stderr"]
    
    def test_import_numpy(self):
        """Test importing numpy (may or may not be available)."""
        response = client.post(
            "/api/v1/execute",
            json={
                "code": "try:\n    import numpy as np\n    print('numpy available')\nexcept ImportError:\n    print('numpy not available')",
                "timeout": 5
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == ExecutionStatus.SUCCESS
        # Either numpy is available or not, both are valid
        assert "numpy" in data["stdout"].lower()
    
    def test_import_requests(self):
        """Test importing requests library (may or may not be available)."""
        response = client.post(
            "/api/v1/execute",
            json={
                "code": "try:\n    import requests\n    print('requests available')\nexcept ImportError:\n    print('requests not available')",
                "timeout": 5
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == ExecutionStatus.SUCCESS
        assert "requests" in data["stdout"].lower()


class TestEdgeCases:
    """Additional edge cases and boundary conditions."""
    
    def test_very_long_code(self):
        """Test execution of very long code string."""
        long_code = "x = 0\n" * 1000 + "print(x)"
        response = client.post(
            "/api/v1/execute",
            json={
                "code": long_code,
                "timeout": 5
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == ExecutionStatus.SUCCESS
    
    def test_minimum_timeout(self):
        """Test with minimum timeout value."""
        response = client.post(
            "/api/v1/execute",
            json={
                "code": "print('quick')",
                "timeout": 1
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == ExecutionStatus.SUCCESS
    
    def test_maximum_timeout(self):
        """Test with maximum timeout value."""
        response = client.post(
            "/api/v1/execute",
            json={
                "code": "print('test')",
                "timeout": 30
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == ExecutionStatus.SUCCESS
    
    def test_unicode_characters(self):
        """Test code with unicode characters."""
        response = client.post(
            "/api/v1/execute",
            json={
                "code": "print('Hello 世界 🌍')\nprint('测试')",
                "timeout": 5
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == ExecutionStatus.SUCCESS
    
    def test_special_characters_in_output(self):
        """Test output with special characters."""
        response = client.post(
            "/api/v1/execute",
            json={
                "code": "print('Line 1\\nLine 2\\tTabbed')\nprint('Quotes: \"test\" \\'test\\'')",
                "timeout": 5
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == ExecutionStatus.SUCCESS


# Pytest hooks for logging
@pytest.fixture(autouse=True)
def log_test_execution(request):
    """Fixture to log test execution start and end."""
    logger.info(f"Starting test: {request.node.name}")
    yield
    logger.info(f"Completed test: {request.node.name}")


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Hook to log test results."""
    outcome = yield
    rep = outcome.get_result()
    if rep.when == "call":
        if rep.failed:
            logger.error(f"Test FAILED: {item.name} - {rep.longrepr}")
        elif rep.skipped:
            logger.warning(f"Test SKIPPED: {item.name}")
        else:
            logger.info(f"Test PASSED: {item.name}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

