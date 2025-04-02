import pytest
import datetime
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from backend.db_connector import AwsDbConnector

# Setup a mock engine for in-memory SQLite testing
@pytest.fixture
def mock_db_connector():
    with patch('backend.db_connector.create_engine') as mock_create_engine:
        # Create an in-memory SQLite database for testing
        engine = create_engine(
            'sqlite:///:memory:',
            connect_args={'check_same_thread': False},
            poolclass=StaticPool
        )
        mock_create_engine.return_value = engine
        
        # Initialize the connector with the mocked engine
        connector = AwsDbConnector(db_url="sqlite:///:memory:")
        connector.engine = engine
        connector.metadata.create_all(engine)
        
        yield connector

def test_init_with_db_url():
    """Test initialization with a provided DB URL"""
    with patch('backend.db_connector.create_engine') as mock_create_engine:
        db_connector = AwsDbConnector(db_url="sqlite:///:memory:")
        mock_create_engine.assert_called_with("sqlite:///:memory:")

def test_init_without_db_url():
    """Test initialization without a DB URL (should use the default from config)"""
    with patch('backend.db_connector.AWS_DB_URL', 'mock_url'), \
         patch('backend.db_connector.create_engine') as mock_create_engine:
        db_connector = AwsDbConnector()
        mock_create_engine.assert_called_with('mock_url')

def test_init_raises_with_no_db_url():
    """Test that initialization raises an error if no DB URL is available"""
    with patch('backend.db_connector.AWS_DB_URL', None):
        with pytest.raises(ValueError, match="Database URL not set"):
            AwsDbConnector()

def test_get_or_create_company_existing(mock_db_connector):
    """Test retrieving an existing company"""
    # First create a company
    company_id = mock_db_connector.get_or_create_company("test@example.com", "Test Company")
    
    # Now try to get the same company
    result = mock_db_connector.get_or_create_company("test@example.com", "Test Company")
    
    # The result should be the same company_id
    assert result == company_id

def test_get_or_create_company_new(mock_db_connector):
    """Test creating a new company"""
    # Create a new company
    company_id = mock_db_connector.get_or_create_company("test@example.com", "New Test Company")
    
    # Verify it was created by checking if we can retrieve it
    with mock_db_connector.engine.connect() as connection:
        result = connection.execute(
            mock_db_connector.companies_table.select().where(
                mock_db_connector.companies_table.c.company_id == company_id
            )
        ).fetchone()
    
    assert result is not None
    assert result.company_name == "New Test Company"
    assert result.created_by == "test@example.com"

def test_add_user_company_mapping_new(mock_db_connector):
    """Test adding a new user-company mapping"""
    # First create a company
    company_id = mock_db_connector.get_or_create_company("test@example.com", "Test Company")
    
    # Add a new user to the company
    mock_db_connector.add_user_company_mapping("new_user@example.com", company_id)
    
    # Verify the mapping was created
    with mock_db_connector.engine.connect() as connection:
        result = connection.execute(
            mock_db_connector.user_companies_table.select().where(
                mock_db_connector.user_companies_table.c.user_email == "new_user@example.com",
                mock_db_connector.user_companies_table.c.company_id == company_id
            )
        ).fetchone()
    
    assert result is not None
    assert result.role == "admin"  # Default role

def test_add_user_company_mapping_existing(mock_db_connector):
    """Test adding a user-company mapping that already exists"""
    # First create a company and add a user
    company_id = mock_db_connector.get_or_create_company("test@example.com", "Test Company")
    mock_db_connector.add_user_company_mapping("user@example.com", company_id)
    
    # Try to add the same mapping again
    mock_db_connector.add_user_company_mapping("user@example.com", company_id)
    
    # Verify there's still only one mapping
    with mock_db_connector.engine.connect() as connection:
        count = connection.execute(
            mock_db_connector.user_companies_table.select().where(
                mock_db_connector.user_companies_table.c.user_email == "user@example.com",
                mock_db_connector.user_companies_table.c.company_id == company_id
            )
        ).fetchall()
    
    assert len(count) == 1

def test_update_last_sync_time(mock_db_connector):
    """Test updating the last sync time for a user-company"""
    # First create a company and add a user
    company_id = mock_db_connector.get_or_create_company("test@example.com", "Test Company")
    mock_db_connector.add_user_company_mapping("user@example.com", company_id)
    
    # Update the last sync time
    mock_db_connector.update_last_sync_time("user@example.com", company_id)
    
    # Verify the last sync time was updated
    with mock_db_connector.engine.connect() as connection:
        result = connection.execute(
            mock_db_connector.user_companies_table.select().where(
                mock_db_connector.user_companies_table.c.user_email == "user@example.com",
                mock_db_connector.user_companies_table.c.company_id == company_id
            )
        ).fetchone()
    
    assert result is not None
    assert result.last_sync_time is not None

def test_get_companies_for_user(mock_db_connector):
    """Test getting all companies for a user"""
    # Create multiple companies for the same user
    company_id1 = mock_db_connector.get_or_create_company("test@example.com", "Company One")
    company_id2 = mock_db_connector.get_or_create_company("test@example.com", "Company Two")
    
    # Add user to both companies
    mock_db_connector.add_user_company_mapping("user@example.com", company_id1)
    mock_db_connector.add_user_company_mapping("user@example.com", company_id2)
    
    # Get companies for the user
    companies = mock_db_connector.get_companies_for_user("user@example.com")
    
    # Verify we got both companies
    assert len(companies) == 2
    assert "Company One" in companies
    assert "Company Two" in companies

def test_get_last_sync_time(mock_db_connector):
    """Test getting the last sync time for a user-company"""
    # First create a company and add a user
    company_id = mock_db_connector.get_or_create_company("test@example.com", "Test Company")
    mock_db_connector.add_user_company_mapping("user@example.com", company_id)
    
    # Initially there should be no sync time
    sync_time = mock_db_connector.get_last_sync_time("user@example.com", company_id)
    assert sync_time is None
    
    # Update the last sync time
    mock_db_connector.update_last_sync_time("user@example.com", company_id)
    
    # Now there should be a sync time
    sync_time = mock_db_connector.get_last_sync_time("user@example.com", company_id)
    assert sync_time is not None
