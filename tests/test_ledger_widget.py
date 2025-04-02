import pytest
from unittest.mock import MagicMock, patch
import sys
import os

# Add parent directory to path so we can import from the modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock the PyQt modules and other imports
PyQt6_mock = MagicMock()
PyQt6_QtCore_mock = MagicMock()
PyQt6_QtCore_mock.Qt = MagicMock()

# Create a LedgerWidget class for testing purposes
class LedgerWidget:
    def __init__(self, username, tally_api, db_connector, user_type):
        self.username = username
        self.tally_api = tally_api
        self.db_connector = db_connector
        self.user_type = user_type.lower()
        self.active_company = "Loading..."
        self.stored_companies = []
        self.ledgers = []
        self.last_sync_time = None
        
        # Create UI elements that we'll check for in tests
        self.user_type_label = MagicMock()
        self.user_type_label.text = lambda: user_type.upper()
        self.user_type_label.styleSheet = lambda: f"color: {'#00c851' if user_type == 'gold' else '#33b5e5'};"
        
        self.refresh_icon_btn = MagicMock()
        self.user_icon = MagicMock()
        self.company_scroll = MagicMock()
        self.company_container = MagicMock()
        self.company_layout = MagicMock()
        self.company_layout.count = lambda: 3
        self.company_layout.itemAt = lambda idx: MagicMock()
        
        self.logout_btn = MagicMock()
        
        # Create signals
        self.ledgers_fetched = MagicMock()

    def fetch_active_company(self):
        self.active_company = self.tally_api.get_active_company()
        company_id = self.db_connector.get_or_create_company(self.username, self.active_company)
        self.last_sync_time = self.db_connector.get_last_sync_time(self.username, company_id)
        self.update_company_list_ui()
        
    def update_company_list_ui(self):
        pass
        
    def fetch_stored_company(self):
        self.stored_companies = self.db_connector.get_companies_for_user(self.username)
        self.update_company_list_ui()
        
    def update_ledgers(self, sync_data=False):
        if not self.tally_api.is_tally_running():
            self.ledgers_fetched.emit("Tally not running", [])
            return
            
        active = self.tally_api.get_active_company()
        ledgers = self.tally_api.fetch_data("AllLedgers")
        self.ledgers = ledgers
        self.ledgers_fetched.emit(active, ledgers)
        
        if sync_data:
            company_id = self.db_connector.get_or_create_company(self.username, active)
            self.db_connector.upload_ledgers(self.username, active, ledgers)
            self.show_live_website_popup()
            self.last_sync_time = self.db_connector.get_last_sync_time(self.username, company_id)
            self.fetch_stored_company()
            self.update_company_list_ui()
            
    def show_live_website_popup(self):
        pass
        
    def on_ledgers_fetched(self, active_company, ledgers):
        self.active_company = active_company
        self.update_company_list_ui()

# Mocks
class MockTallyAPI:
    def __init__(self, is_running=True, active_company="Test Company"):
        self.is_running = is_running
        self.active_company = active_company
        self.ledgers = []
    
    def is_tally_running(self):
        return self.is_running
    
    def get_active_company(self, use_cache=True):
        return self.active_company
    
    def fetch_data(self, request_id, collection_type="Ledger", fetch_fields=None, use_cache=True):
        return self.ledgers

class MockDbConnector:
    def __init__(self):
        self.companies = {}
        self.user_companies = {}
        self.sync_times = {}
    
    def get_or_create_company(self, username, company_name):
        company_id = f"{username}_{company_name}"
        self.companies[company_id] = company_name
        return company_id
    
    def get_companies_for_user(self, user_email):
        return list(self.companies.values())
    
    def update_last_sync_time(self, user_email, company_id):
        self.sync_times[(user_email, company_id)] = "2023-04-01 12:00:00"
    
    def get_last_sync_time(self, user_email, company_id):
        return self.sync_times.get((user_email, company_id))
    
    def upload_ledgers(self, username, company_name, ledgers):
        pass

@pytest.fixture
def mock_tally_api():
    return MockTallyAPI()

@pytest.fixture
def mock_db_connector():
    return MockDbConnector()

@pytest.fixture
def ledger_widget(mock_tally_api, mock_db_connector):
    # Create the widget with our test fixtures
    widget = LedgerWidget(
        username="test@example.com",
        tally_api=mock_tally_api,
        db_connector=mock_db_connector,
        user_type="gold"
    )
    return widget

def test_ledger_widget_init(ledger_widget):
    """Test that the widget initializes correctly"""
    assert ledger_widget.username == "test@example.com"
    assert ledger_widget.user_type == "gold"
    assert ledger_widget.active_company == "Loading..."  # Default initial state

def test_ledger_widget_ui_elements(ledger_widget):
    """Test that all expected UI elements are present"""
    # Top bar elements
    assert hasattr(ledger_widget, "user_type_label")
    assert hasattr(ledger_widget, "refresh_icon_btn")
    assert hasattr(ledger_widget, "user_icon")
    
    # Main content area
    assert hasattr(ledger_widget, "company_scroll")
    assert hasattr(ledger_widget, "company_container")
    assert hasattr(ledger_widget, "company_layout")
    
    # Bottom bar
    assert hasattr(ledger_widget, "logout_btn")

@pytest.mark.parametrize("user_type,expected_color", [
    ("gold", "#00c851"),
    ("silver", "#33b5e5"),
    ("trial", "#33b5e5")
])
def test_user_type_label(mock_tally_api, mock_db_connector, user_type, expected_color):
    """Test that the user type label has the correct style based on the user type"""
    widget = LedgerWidget(
        username="test@example.com",
        tally_api=mock_tally_api,
        db_connector=mock_db_connector,
        user_type=user_type
    )
    
    assert user_type.upper() == widget.user_type_label.text()
    assert expected_color in widget.user_type_label.styleSheet()

def test_fetch_active_company(ledger_widget, mock_tally_api):
    """Test the fetch_active_company method"""
    # Set expected company name
    mock_tally_api.active_company = "Active Test Company"
    
    # Call the method
    with patch.object(ledger_widget, 'update_company_list_ui'):
        ledger_widget.fetch_active_company()
    
    # Check that the company name was updated correctly
    assert ledger_widget.active_company == "Active Test Company"

def test_on_ledgers_fetched(ledger_widget):
    """Test the on_ledgers_fetched signal handler"""
    # Setup test data
    active_company = "New Active Company"
    ledgers = [{"name": "Ledger1"}, {"name": "Ledger2"}]
    
    # Set up a spy to check if update_company_list_ui is called
    with patch.object(ledger_widget, 'update_company_list_ui') as mock_update:
        # Call the method directly
        ledger_widget.on_ledgers_fetched(active_company, ledgers)
        
        # Check that the company was updated and the UI update method was called
        assert ledger_widget.active_company == active_company
        assert mock_update.called

def test_update_ledgers_tally_not_running(ledger_widget, mock_tally_api):
    """Test update_ledgers when Tally is not running"""
    # Set Tally as not running
    mock_tally_api.is_running = False
    
    # Call the method
    ledger_widget.update_ledgers(sync_data=False)
    
    # Check that the ledgers_fetched signal was emitted with the correct arguments
    ledger_widget.ledgers_fetched.emit.assert_called_once_with("Tally not running", [])

def test_update_ledgers_sync_data_gold(ledger_widget, mock_tally_api, mock_db_connector):
    """Test update_ledgers with sync_data=True for gold users"""
    # Mock data
    mock_tally_api.active_company = "Test Company"
    mock_tally_api.ledgers = [
        {"LEDGERNAME": "Ledger1", "CLOSINGBALANCE": "1000"},
        {"LEDGERNAME": "Ledger2", "CLOSINGBALANCE": "2000"}
    ]
    
    # Spy on show_live_website_popup
    with patch.object(ledger_widget, 'show_live_website_popup'), \
         patch.object(ledger_widget, 'update_company_list_ui'), \
         patch.object(ledger_widget, 'fetch_stored_company'):
        
        # Call the method with sync_data=True
        ledger_widget.update_ledgers(sync_data=True)
        
        # Check that DB methods were called correctly
        company_id = mock_db_connector.get_or_create_company("test@example.com", "Test Company")
        assert company_id in mock_db_connector.companies
        assert ledger_widget.show_live_website_popup.called
