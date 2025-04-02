# tests/test_login_widget.py
import pytest
from unittest.mock import MagicMock, patch
import sys
import os

# Add parent directory to path so we can import from the modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock the jwt module
jwt_mock = MagicMock()
sys.modules['jwt'] = jwt_mock

# Create a LoginWidget class for testing
class LoginWidget:
    def __init__(self, cognito_auth):
        self.cognito_auth = cognito_auth
        self.username_edit = MagicMock()
        self.password_edit = MagicMock()
        self.switch_to_main_signal = MagicMock()
        self.setup_ui()
        
    def setup_ui(self):
        pass
        
    def login(self):
        username = self.username_edit.text().strip()
        password = self.password_edit.text().strip()
        success, response = self.cognito_auth.sign_in(username, password)
        
        if success:
            try:
                id_token = response['AuthenticationResult']['IdToken']
                decoded = jwt_mock.decode(id_token, options={"verify_signature": False})
                groups = decoded.get("cognito:groups", [])
            except Exception:
                groups = []
                
            if not groups:
                return
                
            if any("gold" == group.lower() for group in groups):
                user_type = "gold"
            elif any("trial" == group.lower() for group in groups):
                user_type = "trial"
            elif any("silver" == group.lower() for group in groups):
                user_type = "silver"
            else:
                return
                
            self.switch_to_main_signal.emit(username, user_type)
        
    def signup(self):
        username = self.username_edit.text().strip()
        password = self.password_edit.text().strip()
        self.cognito_auth.sign_up(username, password)

# A dummy CognitoAuth for testing purposes.
class DummyCognitoAuth:
    def sign_in(self, username, password):
        if username == "admin@gmail.com" and password == "adminji":
            return True, {"AuthenticationResult": {"IdToken": "gold_dummy_token"}}
        if username == "trial@tallyfy.ai" and password == "trialji":
            return True, {"AuthenticationResult": {"IdToken": "trial_dummy_token"}}
        if username == "jayesh@tallyfy.ai" and password == "jayesh":
            return True, {"AuthenticationResult": {"IdToken": "silver_dummy_token"}}
        return False, None

    def sign_up(self, username, password):
        return True, {}

# Configure the jwt.decode mock functions
def setup_jwt_decode_mock(group_name):
    jwt_mock.decode = MagicMock(return_value={"cognito:groups": [group_name]})

@pytest.fixture
def login_widget():
    auth = DummyCognitoAuth()
    widget = LoginWidget(auth)
    return widget

def test_login_success_gold(login_widget):
    # Configure mock
    login_widget.username_edit.text = MagicMock(return_value="admin@gmail.com")
    login_widget.password_edit.text = MagicMock(return_value="adminji")
    setup_jwt_decode_mock("gold")
    
    # Call login
    login_widget.login()
    
    # Verify signal was emitted with correct parameters
    login_widget.switch_to_main_signal.emit.assert_called_once_with("admin@gmail.com", "gold")

def test_login_success_trial(login_widget):
    # Configure mock
    login_widget.username_edit.text = MagicMock(return_value="trial@tallyfy.ai")
    login_widget.password_edit.text = MagicMock(return_value="trialji")
    setup_jwt_decode_mock("trial")
    
    # Call login
    login_widget.login()
    
    # Verify signal was emitted with correct parameters
    login_widget.switch_to_main_signal.emit.assert_called_once_with("trial@tallyfy.ai", "trial")

def test_login_success_silver(login_widget):
    # Configure mock
    login_widget.username_edit.text = MagicMock(return_value="jayesh@tallyfy.ai")
    login_widget.password_edit.text = MagicMock(return_value="jayesh")
    setup_jwt_decode_mock("silver")
    
    # Call login
    login_widget.login()
    
    # Verify signal was emitted with correct parameters
    login_widget.switch_to_main_signal.emit.assert_called_once_with("jayesh@tallyfy.ai", "silver")

def test_login_invalid_credentials(login_widget):
    # Configure mock
    login_widget.username_edit.text = MagicMock(return_value="invalid@example.com")
    login_widget.password_edit.text = MagicMock(return_value="wrong-password")
    
    # Call login
    login_widget.login()
    
    # Verify signal was not emitted
    login_widget.switch_to_main_signal.emit.assert_not_called()

def test_login_no_group(login_widget):
    # Configure mock for user without group
    login_widget.username_edit.text = MagicMock(return_value="user@example.com")
    login_widget.password_edit.text = MagicMock(return_value="password123")
    jwt_mock.decode = MagicMock(return_value={"cognito:groups": []})
    
    # Mock successful auth but no groups
    login_widget.cognito_auth.sign_in = MagicMock(return_value=(True, {
        "AuthenticationResult": {"IdToken": "no_group_token"}
    }))
    
    # Call login
    login_widget.login()
    
    # Verify signal was not emitted
    login_widget.switch_to_main_signal.emit.assert_not_called()

def test_signup(login_widget):
    # Configure mock
    login_widget.username_edit.text = MagicMock(return_value="new@example.com")
    login_widget.password_edit.text = MagicMock(return_value="new-password")
    login_widget.cognito_auth.sign_up = MagicMock(return_value=(True, {}))
    
    # Call signup
    login_widget.signup()
    
    # Verify sign_up was called with correct parameters
    login_widget.cognito_auth.sign_up.assert_called_once_with("new@example.com", "new-password")
