# Running Tests for Solar Energy Controller

This guide explains how to set up and run the test suite for the Solar Energy Controller integration.

> **Important:** These are **unit tests** that run in a **development environment** (not inside your running Home Assistant instance). They use mocked Home Assistant components to test the code logic.

## Prerequisites

1. **Python 3.10 or later** (required for Home Assistant testing)
2. **pip** (Python package manager)
3. **A separate development environment** (not your running Home Assistant)

## Setup

### 1. Install Test Dependencies

Create a virtual environment and install the required test dependencies:

```bash
# Create a virtual environment (recommended)
python -m venv venv

# Activate the virtual environment
# On Windows (PowerShell):
# If you get execution policy error, run first:
#   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
venv\Scripts\activate
# OR use Command Prompt (cmd) instead:
#   venv\Scripts\activate.bat
# On Linux/Mac:
source venv/bin/activate

# Install test dependencies
pip install pytest pytest-asyncio pytest-homeassistant-custom-component
```

### 2. Install Home Assistant Core (for testing)

The tests require Home Assistant core to be available:

```bash
pip install homeassistant
```

## Running Tests

### Run All Tests

From the project root directory, run:

```bash
pytest
```

### Run Specific Test Files

Run a specific test file:

```bash
# Test initialization
pytest tests/test_init.py

# Test config flow
pytest tests/test_config_flow.py

# Test coordinator
pytest tests/test_coordinator.py

# Test PID controller
pytest tests/test_pid.py

# Test number entities
pytest tests/test_number.py

# Test select entities
pytest tests/test_select.py

# Test sensor entities
pytest tests/test_sensor.py

# Test switch entities
pytest tests/test_switch.py
```

### Run Specific Test Functions

Run a specific test function:

```bash
pytest tests/test_init.py::test_async_setup
```

### Run Tests with Verbose Output

Get more detailed output:

```bash
pytest -v
```

### Run Tests with Coverage

To see code coverage:

```bash
pip install pytest-cov
pytest --cov=custom_components.solar_energy_controller --cov-report=html
```

This will generate an HTML coverage report in `htmlcov/index.html`.

### Run Tests in Parallel (faster)

```bash
pip install pytest-xdist
pytest -n auto
```

## Test Structure

The test suite is organized as follows:

- `tests/conftest.py` - Shared pytest fixtures and configuration
- `tests/test_init.py` - Tests for module initialization
- `tests/test_config_flow.py` - Tests for configuration flow
- `tests/test_coordinator.py` - Tests for the coordinator
- `tests/test_pid.py` - Tests for PID controller logic
- `tests/test_number.py` - Tests for number entities
- `tests/test_select.py` - Tests for select entities
- `tests/test_sensor.py` - Tests for sensor entities
- `tests/test_switch.py` - Tests for switch entities

## Running Tests in Docker (Recommended for Windows)

If you're on Windows and having issues with dependencies, you can run tests in Docker:

### Quick Start

1. **Build the test image:**
   ```bash
   docker build -f Dockerfile.test -t solar-energy-controller-tests .
   ```

2. **Run the tests:**
   ```bash
   docker run --rm solar-energy-controller-tests
   ```

   Or on Windows, use the batch file:
   ```cmd
   run-tests.bat
   ```

### What This Does

- Creates a Linux container with Python 3.11
- Installs all test dependencies (including homeassistant)
- Runs all tests in a clean environment
- Automatically cleans up after running

### Run Specific Tests

To run specific test files, override the CMD:

```bash
docker run --rm solar-energy-controller-tests pytest tests/test_pid.py -v
```

### Interactive Mode

To get a shell inside the container for debugging:

```bash
docker run -it --rm solar-energy-controller-tests /bin/bash
```

Then you can run commands manually:
```bash
pytest -v
pytest tests/test_pid.py -v
```

## Running Tests vs Testing in Home Assistant

### Unit Tests (This Guide)
- **Where:** Run on your development machine (separate from Home Assistant)
- **What:** Tests the code logic using mocked Home Assistant components
- **Purpose:** Verify code works correctly before deployment
- **Requires:** Python, pytest, and test dependencies installed locally

### Manual Testing in Home Assistant
- **Where:** Inside your running Home Assistant instance
- **What:** Install the integration and test it manually through the UI
- **Purpose:** Verify real-world functionality with actual entities
- **How:**
  1. Install the integration via HACS or manual copy
  2. Add it through Settings → Devices & Services
  3. Configure with real entities
  4. Test all features manually

**Both approaches are important:**
- Unit tests catch bugs early in development
- Manual testing in HA verifies everything works with real devices

## Troubleshooting

### Import Errors

If you get import errors, make sure you're running tests from the project root directory and that the `custom_components` directory is in your Python path.

### Home Assistant Version Issues

If you encounter version conflicts, you may need to install a specific version of Home Assistant:

```bash
pip install "homeassistant>=2023.9.0"
```

### Missing Dependencies

If tests fail with missing module errors, install the missing dependencies:

```bash
pip install -r requirements.txt  # if you have one
# or install manually:
pip install pytest pytest-asyncio pytest-homeassistant-custom-component homeassistant
```

## Continuous Integration

For CI/CD pipelines, you can use:

```bash
# Install dependencies
pip install pytest pytest-asyncio pytest-homeassistant-custom-component homeassistant

# Run tests
pytest -v --tb=short
```

## Writing New Tests

When adding new tests:

1. Follow the existing test structure
2. Use async test functions for async code
3. Mock external dependencies (Home Assistant, entities, etc.)
4. Test both success and error cases
5. Use descriptive test function names starting with `test_`

Example:

```python
async def test_new_feature_success():
    """Test that new feature works correctly."""
    # Arrange
    # Act
    # Assert
```

