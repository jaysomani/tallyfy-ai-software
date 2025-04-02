import pytest
import sys
import os
from unittest.mock import MagicMock, patch

# Add the project directory to the Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import project modules after setting up the path
from backend.tally_api import TallyAPI
from backend.db_connector import AwsDbConnector
from backend.cognito_auth import CognitoAuth

# Generic fixtures that can be used across different test modules

@pytest.fixture
def mock_tally_api():
    """Create a mock TallyAPI instance"""
    mock_api = MagicMock(spec=TallyAPI)
    mock_api.is_tally_running.return_value = True
    mock_api.get_active_company.return_value = "Test Company"
    mock_api.fetch_data.return_value = []
    return mock_api

@pytest.fixture
def mock_db_connector():
    """Create a mock AwsDbConnector instance"""
    mock_db = MagicMock(spec=AwsDbConnector)
    mock_db.get_companies_for_user.return_value = ["Test Company"]
    mock_db.get_or_create_company.return_value = "test_company_id"
    return mock_db

@pytest.fixture
def mock_cognito_auth():
    """Create a mock CognitoAuth instance"""
    mock_auth = MagicMock(spec=CognitoAuth)
    # Default success response for sign_in
    mock_auth.sign_in.return_value = (True, {
        "AuthenticationResult": {
            "IdToken": "test_token",
            "AccessToken": "test_access",
            "RefreshToken": "test_refresh"
        }
    })
    # Default success response for sign_up
    mock_auth.sign_up.return_value = (True, {
        "UserConfirmed": False,
        "UserSub": "test_user_sub"
    })
    return mock_auth

@pytest.fixture
def app_instance():
    """Create a PyQt application instance"""
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
    # This will be executed after the test is complete
    # Add cleanup if needed

@pytest.fixture
def qtbot_package(app_instance):
    """Fixture to get a QtBot with an existing QApplication instance"""
    # This ensures we're using the same QApplication instance
    return app_instance 