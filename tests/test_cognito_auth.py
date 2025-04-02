import pytest
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError

from backend.cognito_auth import CognitoAuth

@pytest.fixture
def cognito_auth():
    """Create a CognitoAuth instance with mocked boto3 client"""
    with patch('boto3.client') as mock_client:
        auth = CognitoAuth('test-pool-id', 'test-client-id', 'us-east-1')
        # Access the mocked client
        auth.client = mock_client.return_value
        yield auth

def test_init():
    """Test the initialization of CognitoAuth"""
    with patch('boto3.client') as mock_client:
        auth = CognitoAuth('test-pool-id', 'test-client-id', 'us-east-1')
        
        mock_client.assert_called_once_with('cognito-idp', region_name='us-east-1')
        assert auth.user_pool_id == 'test-pool-id'
        assert auth.client_id == 'test-client-id'

def test_sign_in_success(cognito_auth):
    """Test successful sign-in"""
    # Mock the successful response
    mock_response = {
        'AuthenticationResult': {
            'IdToken': 'test-id-token',
            'AccessToken': 'test-access-token',
            'RefreshToken': 'test-refresh-token'
        }
    }
    cognito_auth.client.initiate_auth.return_value = mock_response
    
    # Test sign-in
    success, response = cognito_auth.sign_in('test@example.com', 'password')
    
    # Assertions
    assert success is True
    assert response == mock_response
    cognito_auth.client.initiate_auth.assert_called_once_with(
        ClientId='test-client-id',
        AuthFlow='USER_PASSWORD_AUTH',
        AuthParameters={
            'USERNAME': 'test@example.com',
            'PASSWORD': 'password'
        }
    )

def test_sign_in_failure(cognito_auth):
    """Test failed sign-in"""
    # Mock the exception
    error_response = {
        'Error': {
            'Code': 'NotAuthorizedException',
            'Message': 'Incorrect username or password.'
        }
    }
    exception = ClientError(error_response, 'InitiateAuth')
    cognito_auth.client.initiate_auth.side_effect = exception
    
    # Test sign-in
    success, response = cognito_auth.sign_in('test@example.com', 'wrong-password')
    
    # Assertions
    assert success is False
    assert response is None
    cognito_auth.client.initiate_auth.assert_called_once()

def test_sign_up_success(cognito_auth):
    """Test successful sign-up"""
    # Mock the successful response
    mock_response = {
        'UserConfirmed': False,
        'UserSub': 'test-user-sub'
    }
    cognito_auth.client.sign_up.return_value = mock_response
    
    # Test sign-up
    success, response = cognito_auth.sign_up('test@example.com', 'password')
    
    # Assertions
    assert success is True
    assert response == mock_response
    cognito_auth.client.sign_up.assert_called_once_with(
        ClientId='test-client-id',
        Username='test@example.com',
        Password='password',
        UserAttributes=[{'Name': 'email', 'Value': 'test@example.com'}]
    )

def test_sign_up_failure(cognito_auth):
    """Test failed sign-up"""
    # Mock the exception
    error_response = {
        'Error': {
            'Code': 'UsernameExistsException',
            'Message': 'User already exists'
        }
    }
    exception = ClientError(error_response, 'SignUp')
    cognito_auth.client.sign_up.side_effect = exception
    
    # Test sign-up
    success, response = cognito_auth.sign_up('existing@example.com', 'password')
    
    # Assertions
    assert success is False
    assert response is None
    cognito_auth.client.sign_up.assert_called_once()

def test_sign_in_network_error(cognito_auth):
    """Test sign-in with network error"""
    # Mock a connection error
    error_response = {
        'Error': {
            'Code': 'ServiceError',
            'Message': 'Network connection issue'
        }
    }
    exception = ClientError(error_response, 'InitiateAuth')
    cognito_auth.client.initiate_auth.side_effect = exception
    
    # Test sign-in
    success, response = cognito_auth.sign_in('test@example.com', 'password')
    
    # Assertions
    assert success is False
    assert response is None

def test_sign_up_malformed_request(cognito_auth):
    """Test sign-up with malformed request (e.g., invalid email)"""
    # Mock the exception for invalid parameters
    error_response = {
        'Error': {
            'Code': 'InvalidParameterException',
            'Message': 'Invalid email format'
        }
    }
    exception = ClientError(error_response, 'SignUp')
    cognito_auth.client.sign_up.side_effect = exception
    
    # Test sign-up
    success, response = cognito_auth.sign_up('invalid-email', 'password')
    
    # Assertions
    assert success is False
    assert response is None 