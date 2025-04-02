import pytest
import sys
import os
from unittest.mock import patch, MagicMock
import time

# Add parent directory to path so we can import from the main module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock the modules before importing main
with patch.dict('sys.modules', {
    'gui.main_window': MagicMock(),
    'backend.tally_api': MagicMock(),
    'backend.db_connector': MagicMock(),
    'backend.cognito_auth': MagicMock(),
    'PyQt6.QtWidgets': MagicMock()
}):
    # Now we can import main
    import main

@pytest.fixture
def mock_dependencies():
    """Mock all dependencies needed for main module tests"""
    with patch('subprocess.Popen') as mock_popen, \
         patch('time.sleep') as mock_sleep, \
         patch('backend.tally_api.TallyAPI') as mock_tally_api, \
         patch('backend.db_connector.AwsDbConnector') as mock_db_connector, \
         patch('backend.cognito_auth.CognitoAuth') as mock_cognito_auth, \
         patch('PyQt6.QtWidgets.QApplication') as mock_app, \
         patch('gui.main_window.MainWindow') as mock_window:
        
        # Return all our mocks as a dictionary
        yield {
            'popen': mock_popen,
            'sleep': mock_sleep,
            'tally_api': mock_tally_api,
            'db_connector': mock_db_connector,
            'cognito_auth': mock_cognito_auth,
            'app': mock_app,
            'window': mock_window,
        }

def test_main_function_exists():
    """Basic test to verify that the main function exists"""
    assert callable(main.main)

@patch('subprocess.Popen')
@patch('time.sleep')
@patch('backend.tally_api.TallyAPI')
@patch('backend.db_connector.AwsDbConnector')
@patch('backend.cognito_auth.CognitoAuth')
@patch('PyQt6.QtWidgets.QApplication')
@patch('gui.main_window.MainWindow')
@patch('sys.argv', ['main.py'])
@patch('sys.exit')
@pytest.mark.skip(reason="Main tests need additional setup")
def test_main_basic_execution(mock_exit, mock_window, mock_app, mock_cognito, 
                                mock_db, mock_tally, mock_sleep, mock_popen):
    """Test that main can be executed without errors"""
    # Mock QApplication instance
    mock_app_instance = MagicMock()
    mock_app.return_value = mock_app_instance
    
    # Mock window instance
    mock_window_instance = MagicMock()
    mock_window.return_value = mock_window_instance
    
    # Mock config constants
    main.COGNITO_USER_POOL_ID = 'test-pool'
    main.COGNITO_CLIENT_ID = 'test-client'
    main.COGNITO_REGION = 'us-east-1'
    
    # Call main function
    main.main()
    
    # Verify Flask server was started
    mock_popen.assert_called_once()
    
    # Verify sleep was called to wait for Flask server
    mock_sleep.assert_called_once()
    
    # Verify all major dependencies were initialized
    mock_tally.assert_called_once()
    mock_db.assert_called_once()
    mock_cognito.assert_called_once()
    
    # Verify main window was created and shown
    mock_window.assert_called_once()
    mock_window_instance.show.assert_called_once()
    
    # Verify application exec was called
    mock_app_instance.exec.assert_called_once()

@pytest.mark.skip(reason="Main tests need additional setup")
def test_main_success(mock_dependencies):
    """Test that main initializes all required components and runs the app"""
    # Mock QApplication instance
    mock_app_instance = MagicMock()
    mock_dependencies['app'].return_value = mock_app_instance
    
    # Mock window instance
    mock_window_instance = MagicMock()
    mock_dependencies['window'].return_value = mock_window_instance
    
    # Patch sys.argv to avoid any dependency on command line arguments
    with patch('sys.argv', ['main.py']):
        # Call main function
        main.main()
    
    # Verify Flask server was started
    mock_dependencies['popen'].assert_called_once()
    assert 'flask_server.py' in str(mock_dependencies['popen'].call_args)
    
    # Verify sleep was called to wait for Flask server
    mock_dependencies['sleep'].assert_called_once_with(2)
    
    # Verify all dependencies were initialized
    mock_dependencies['tally_api'].assert_called_once()
    mock_dependencies['db_connector'].assert_called_once()
    mock_dependencies['cognito_auth'].assert_called_once_with(
        main.COGNITO_USER_POOL_ID, main.COGNITO_CLIENT_ID, main.COGNITO_REGION
    )
    
    # Verify main window was created and shown
    mock_dependencies['window'].assert_called_once()
    mock_window_instance.show.assert_called_once()
    
    # Verify application exec was called
    mock_app_instance.exec.assert_called_once()

@pytest.mark.skip(reason="Main tests need additional setup")
def test_main_dependency_error(mock_dependencies):
    """Test that main handles errors in initializing dependencies"""
    # Make db_connector raise an exception
    mock_dependencies['db_connector'].side_effect = Exception("DB connection error")
    
    # Patch sys.exit to avoid exiting the test
    with patch('sys.exit') as mock_exit, patch('sys.argv', ['main.py']):
        main.main()
    
    # Verify error logging and exit with non-zero code
    mock_exit.assert_called_once_with(1)
    
    # Verify Flask process termination is attempted
    # This might be tricky to test directly, but we can check the flask_process is in locals

@pytest.mark.skip(reason="Main tests need additional setup")
def test_main_flask_server_cleanup(mock_dependencies):
    """Test that Flask server is cleaned up even if an error occurs"""
    # Mock Flask process
    mock_flask_process = MagicMock()
    mock_dependencies['popen'].return_value = mock_flask_process
    
    # Make app.exec raise an exception
    mock_app_instance = MagicMock()
    mock_app_instance.exec.side_effect = Exception("App exec error")
    mock_dependencies['app'].return_value = mock_app_instance
    
    # Call main with patched sys.exit
    with patch('sys.exit') as mock_exit, patch('sys.argv', ['main.py']):
        main.main()
    
    # Verify Flask process was terminated
    mock_flask_process.terminate.assert_called_once()
    mock_flask_process.wait.assert_called_once() 