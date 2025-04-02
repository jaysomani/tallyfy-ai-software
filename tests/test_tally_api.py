import pytest
import time
import xml.etree.ElementTree as ET
from unittest.mock import Mock, patch, MagicMock
import requests

from backend.tally_api import TallyAPI

@pytest.fixture
def tally_api():
    """Create a TallyAPI instance with mocked requests"""
    return TallyAPI(server_url='http://localhost:9000')

def test_init():
    """Test the initialization of TallyAPI"""
    api = TallyAPI(server_url='http://example.com', cache_timeout=20)
    assert api.server_url == 'http://example.com'
    assert api.cache_timeout == 20
    assert api.cache == {}
    assert api.company_cache is None
    assert api.company_cache_time == 0

def test_is_tally_running_success(tally_api):
    """Test checking if Tally is running (successful case)"""
    with patch('requests.get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        assert tally_api.is_tally_running() is True
        mock_get.assert_called_once_with('http://localhost:9000', timeout=3)

def test_is_tally_running_failure(tally_api):
    """Test checking if Tally is running (failure cases)"""
    # Test with non-200 response
    with patch('requests.get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        assert tally_api.is_tally_running() is False
    
    # Test with request exception
    with patch('requests.get') as mock_get:
        mock_get.side_effect = requests.exceptions.RequestException()
        
        assert tally_api.is_tally_running() is False

def test_send_request_tally_not_running(tally_api):
    """Test send_request when Tally is not running"""
    with patch.object(tally_api, 'is_tally_running', return_value=False):
        result = tally_api.send_request('<XML>')
        assert result is None

def test_send_request_success(tally_api):
    """Test send_request with a successful response"""
    with patch.object(tally_api, 'is_tally_running', return_value=True), \
         patch('requests.post') as mock_post, \
         patch.object(tally_api, 'clean_xml', return_value='<CLEANED_XML>'):
        
        mock_response = Mock()
        mock_response.text = '<XML_RESPONSE>'
        mock_post.return_value = mock_response
        
        result = tally_api.send_request('<XML_REQUEST>')
        
        mock_post.assert_called_once_with(
            'http://localhost:9000',
            data='<XML_REQUEST>',
            headers={'Content-Type': 'text/xml'}
        )
        tally_api.clean_xml.assert_called_once_with('<XML_RESPONSE>')
        assert result == '<CLEANED_XML>'

def test_send_request_exception(tally_api):
    """Test send_request when an exception occurs"""
    with patch.object(tally_api, 'is_tally_running', return_value=True), \
         patch('requests.post') as mock_post:
        
        mock_post.side_effect = requests.exceptions.RequestException('Connection error')
        
        result = tally_api.send_request('<XML_REQUEST>')
        
        assert result is None

@patch('time.time', return_value=1000)  # Mock current time
def test_get_active_company_from_cache(mock_time, tally_api):
    """Test get_active_company returns cached result when available"""
    # Setup cache
    tally_api.company_cache = "Test Company"
    tally_api.company_cache_time = 995  # 5 seconds ago
    
    # Cache should be used because cache_timeout is 10 by default
    company = tally_api.get_active_company(use_cache=True)
    assert company == "Test Company"
    
    # No requests should have been made
    with patch('backend.tally_api.TallyAPI.send_request') as mock_send:
        company = tally_api.get_active_company(use_cache=True)
        assert company == "Test Company"
        mock_send.assert_not_called()

@patch('time.time', return_value=1000)  # Mock current time
def test_get_active_company_expired_cache(mock_time, tally_api):
    """Test get_active_company fetches new data when cache is expired"""
    # Setup expired cache
    tally_api.company_cache = "Old Company"
    tally_api.company_cache_time = 985  # 15 seconds ago (beyond the 10s cache_timeout)
    
    with patch.object(tally_api, 'send_request') as mock_send:
        mock_send.return_value = '<ENVELOPE><RESULT>New Company</RESULT></ENVELOPE>'
        
        company = tally_api.get_active_company(use_cache=True)
        
        mock_send.assert_called_once()
        assert company == "New Company"
        assert tally_api.company_cache == "New Company"
        assert tally_api.company_cache_time == 1000

def test_get_active_company_no_cache(tally_api):
    """Test get_active_company fetches data when use_cache=False"""
    with patch.object(tally_api, 'send_request') as mock_send:
        mock_send.return_value = '<ENVELOPE><RESULT>Fresh Company</RESULT></ENVELOPE>'
        
        company = tally_api.get_active_company(use_cache=False)
        
        mock_send.assert_called_once()
        assert company == "Fresh Company"

def test_get_active_company_tally_not_responding(tally_api):
    """Test get_active_company when Tally doesn't respond"""
    with patch.object(tally_api, 'send_request', return_value=None):
        company = tally_api.get_active_company(use_cache=False)
        
        assert company == "Unknown (Tally not responding)"

def test_get_active_company_parse_error(tally_api):
    """Test get_active_company when there's a parsing error"""
    with patch.object(tally_api, 'send_request', return_value='<INVALID>XML<INVALID>'), \
         patch.object(ET, 'fromstring') as mock_fromstring:
        
        mock_fromstring.side_effect = ET.ParseError("XML parsing error")
        
        company = tally_api.get_active_company(use_cache=False)
        
        assert company == "Unknown (Parsing Error)"

@patch('time.time', return_value=1000)  # Mock current time
def test_fetch_data_from_cache(mock_time, tally_api):
    """Test fetch_data returns cached data when available"""
    # Setup cache
    cached_data = [{"name": "Test Ledger"}]
    tally_api.cache = {"TestRequest": (995, cached_data)}  # 5 seconds ago
    
    result = tally_api.fetch_data("TestRequest", use_cache=True)
    
    assert result == cached_data
    assert mock_time.call_count == 1  # Only called once to check cache time

@patch('time.time', return_value=1000)  # Mock current time
def test_fetch_data_expired_cache(mock_time, tally_api):
    """Test fetch_data fetches new data when cache is expired"""
    # Setup expired cache
    cached_data = [{"name": "Old Ledger"}]
    tally_api.cache = {"TestRequest": (985, cached_data)}  # 15 seconds ago
    
    with patch.object(tally_api, 'send_request') as mock_send, \
         patch.object(ET, 'fromstring') as mock_fromstring:
        
        # Mock response parsing
        mock_root = MagicMock()
        mock_fromstring.return_value = mock_root
        
        # Setup response data
        mock_send.return_value = '<XML>New Data</XML>'
        
        # Call fetch_data
        tally_api.fetch_data("TestRequest", use_cache=True)
        
        # Verify new data was fetched
        mock_send.assert_called_once()
        mock_fromstring.assert_called_once_with('<XML>New Data</XML>')

def test_fetch_data_no_response(tally_api):
    """Test fetch_data when no response is received"""
    with patch.object(tally_api, 'send_request', return_value=None):
        result = tally_api.fetch_data("TestRequest", use_cache=False)
        
        assert result == []  # Should return empty list

def test_fetch_data_parse_error(tally_api):
    """Test fetch_data when there's a parsing error"""
    with patch.object(tally_api, 'send_request', return_value='<INVALID>XML<INVALID>'), \
         patch.object(ET, 'fromstring') as mock_fromstring, \
         patch('backend.tally_api.LET') as mock_lxml:
        
        # Mock ElementTree parse error
        mock_fromstring.side_effect = ET.ParseError("XML parsing error")
        
        # Mock lxml parse error as well
        mock_parser = MagicMock()
        mock_lxml.XMLParser.return_value = mock_parser
        mock_lxml.fromstring.side_effect = Exception("lxml error")
        
        result = tally_api.fetch_data("TestRequest", use_cache=False)
        
        assert result == []  # Should return empty list on parse error 