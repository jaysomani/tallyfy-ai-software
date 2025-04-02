# Tally Connector Tests

This directory contains unit and integration tests for the Tally Connector application.

## Test Structure

- `conftest.py` - Common pytest fixtures shared across test modules
- `test_cognito_auth.py` - Tests for the CognitoAuth class (authentication)
- `test_db_connector.py` - Tests for the AwsDbConnector class (database operations)
- `test_tally_api.py` - Tests for the TallyAPI class (communication with Tally)
- `test_ledger_widget.py` - Tests for the LedgerWidget UI component
- `test_login_widget.py` - Tests for the LoginWidget UI component
- `test_flask_server.py` - Tests for the Flask server API endpoints
- `test_main.py` - Integration tests for the main application flow

## Running Tests

### Prerequisites

Make sure you have all the required dependencies installed:

```bash
pip install pytest pytest-qt pytest-mock
```

### Running All Tests

To run all tests from the project root directory:

```bash
pytest -v tests/
```

### Running Specific Test Files

To run tests from a specific test file:

```bash
pytest -v tests/test_tally_api.py
```

### Running Specific Tests

To run a specific test function:

```bash
pytest -v tests/test_tally_api.py::test_is_tally_running_success
```

## Mocking Strategy

The tests use mocks and fixtures to isolate components:

1. **Database Connections**: All database connections are mocked to avoid requiring a real database.
2. **Tally Communication**: Communication with Tally is mocked to avoid requiring a running Tally instance.
3. **AWS Cognito**: AWS Cognito calls are mocked to avoid requiring real AWS credentials.
4. **UI Components**: PyQt UI components are tested using pytest-qt.

## Adding New Tests

When adding new tests:

1. Use the existing mocks and fixtures from `conftest.py` when possible.
2. Follow the naming convention of `test_*.py` for files and `test_*` for test functions.
3. Add docstrings to describe what each test is verifying.
4. Use parameterized tests for testing multiple similar cases.

## Test Coverage

To measure test coverage, run:

```bash
pytest --cov=. tests/
```

For a detailed HTML report:

```bash
pytest --cov=. --cov-report=html tests/
```

This will generate a `htmlcov` directory with detailed coverage information. 