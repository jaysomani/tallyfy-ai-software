import datetime
import logging
from sqlalchemy import create_engine, Table, Column, Integer, String, MetaData, DateTime, JSON, select, update
from sqlalchemy.exc import SQLAlchemyError
from backend.config import AWS_DB_URL, get_company_table_name

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

class AwsDbConnector:
    """
    Handles connection to the AWS PostgreSQL database using SQLAlchemy,
    and stores data according to our multi-tenant architecture.
    """
    def __init__(self, db_url=None):
        self.db_url = db_url or AWS_DB_URL
        if not self.db_url:
            raise ValueError("Database URL not set")
        self.engine = create_engine(self.db_url)
        self.metadata = MetaData()
        self.define_tables()
        self.metadata.create_all(self.engine)
        logging.info("AWS database connector initialized.")

    def define_tables(self):
        # Companies table
        self.companies_table = Table(
            'companies', self.metadata,
            Column('company_id', String, primary_key=True),
            Column('company_name', String(255), nullable=False),
            Column('created_by', String(255), nullable=False),
            Column('created_at', DateTime, default=lambda: datetime.datetime.now(IST))
        )
        # User-companies mapping table
        self.user_companies_table = Table(
            'user_companies', self.metadata,
            Column('id', Integer, primary_key=True, autoincrement=True),
            Column('user_email', String(255), nullable=False),
            Column('company_id', String, nullable=False),
            Column('role', String(50), nullable=True),
            Column('last_sync_time', DateTime)
        )
        # Updated Ledgers table with an extra JSON column for dynamic extra fields
        self.ledger_table = Table(
            'ledgers', self.metadata,
            Column('ledger_id', Integer, primary_key=True, autoincrement=True),
            Column('company_id', String, nullable=False),
            Column('description', String(255), nullable=False),
            Column('closing_balance', String(50), nullable=False),
            Column('timestamp', DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc)),
            Column('extra_data', JSON, nullable=True)  # New column to store extra fields
        )

                # Define the licenses table.
        self.licenses_table = Table(
            'licenses', self.metadata,
            Column('id', Integer, primary_key=True),
            Column('licenseKey', String, nullable=False),
            Column('userId', String, nullable=False),
            Column('validTill', DateTime, nullable=False),
            Column('status', String, nullable=False),
            Column('hardwareId', String, nullable=True),
            Column('createdAt', DateTime, default=lambda: datetime.datetime.now(IST)),
            Column('updatedAt', DateTime, default=lambda: datetime.datetime.now(IST),
                   onupdate=lambda: datetime.datetime.now(IST)),
            Column('detectedhardwareid', String, nullable=True)
        )

        self.users_table = Table(
            'users', self.metadata,
            Column('id', Integer, primary_key=True, autoincrement=True),
            Column('cognitoid', String, nullable=False),
            Column('username', String, nullable=False),
            Column('email', String, nullable=False, unique=True),
            Column('password', String, nullable=True),
            Column('createdAt', DateTime, default=lambda: datetime.datetime.now(IST)),
            Column('updatedAt', DateTime, default=lambda: datetime.datetime.now(IST),
                   onupdate=lambda: datetime.datetime.now(IST))
        )

    def create_user_if_not_exists(self, user_email):
        stmt = select(self.users_table.c.email).where(self.users_table.c.email == user_email)
        with self.engine.connect() as connection:
            result = connection.execute(stmt).fetchone()
        if not result:
            ins = self.users_table.insert().values(
                email=user_email,
                username=user_email,   # Use the email as the username (or provide another value)
                cognitoid=user_email,
                password="test"   # or your actual cognito id value
            )
            with self.engine.begin() as connection:
                connection.execute(ins)
            logging.info("Created new user record for %s", user_email)

    def update_detected_hardware(self, user_email, new_hwid):
        """Updates the detectedHardwareId column for the given user."""
        now = datetime.datetime.now(datetime.timezone.utc)
        stmt = update(self.licenses_table).where(
            self.licenses_table.c.userId == user_email
        ).values(
            detectedhardwareid=new_hwid,
            updatedAt=now
        )
        with self.engine.begin() as connection:
            connection.execute(stmt)
        logging.info("Detected hardware updated for user %s", user_email)

    def update_license_hardware(self, user_email, hardware_id):
        """Update the hardwareId column in the licenses table for the given user."""
        now = datetime.datetime.now(datetime.timezone.utc)
        stmt = update(self.licenses_table).where(
            self.licenses_table.c.userId == user_email
        ).values(
            hardwareId=hardware_id,
            updatedAt=now
        )
        with self.engine.begin() as connection:
            connection.execute(stmt)
        logging.info("License hardware updated for user %s", user_email)
    
    def get_license_hardware(self, user_email):
        """Retrieves the registered hardwareId and detectedHardwareId for the user."""
        stmt = select(self.licenses_table.c.hardwareId, self.licenses_table.c.detectedhardwareid).where(
            self.licenses_table.c.userId == user_email
        )
        with self.engine.connect() as connection:
            result = connection.execute(stmt).fetchone()
        if result:
            return result[0], result[1]
        return None, None
    
    def create_license_record(self, user_email, hardware_id):
        """
        Creates a new license record for the given user with the current hardware_id.
        You can customize the default values for licenseKey, validTill, and status as needed.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        # You may decide on default values; below is an example.
        ins = self.licenses_table.insert().values(
            licenseKey="default_key",        # or generate one as needed
            userId=user_email,
            validTill=now + datetime.timedelta(days=365),  # e.g., 1-year license
            status="active",
            hardwareId=hardware_id,
            detectedhardwareid=None,
            createdAt=now,
            updatedAt=now
        )
        with self.engine.begin() as connection:
            connection.execute(ins)
        logging.info("Created new license record for user %s with hardware id %s", user_email, hardware_id)


    def get_or_create_company(self, username, company_name):
        """
        Check if a company record exists; if not, create it.
        """
        company_id = get_company_table_name(username, company_name)
        with self.engine.connect() as connection:
            stmt = select(self.companies_table.c.company_id).where(self.companies_table.c.company_id == company_id)
            result = connection.execute(stmt).fetchone()
        if result:
            logging.info("Company '%s' already exists.", company_id)
            return company_id
        ins = self.companies_table.insert().values(
            company_id=company_id,
            company_name=company_name,
            created_by=username,
            created_at=datetime.datetime.now(IST)
        )
        with self.engine.begin() as connection:
            connection.execute(ins)
        logging.info("Created new company '%s' for user '%s'.", company_name, username)
        return company_id

    def add_user_company_mapping(self, user_email, company_id, role='admin'):
        """
        Add an entry to the user_companies table if not already present.
        """
        with self.engine.connect() as connection:
            stmt = select(self.user_companies_table).where(
                self.user_companies_table.c.user_email == user_email,
                self.user_companies_table.c.company_id == company_id
            )
            result = connection.execute(stmt).fetchone()
        if result:
            logging.info("User-company mapping for '%s' and '%s' exists.", user_email, company_id)
            return
        ins = self.user_companies_table.insert().values(
            user_email=user_email,
            company_id=company_id,
            role=role
        )
        with self.engine.begin() as connection:
            connection.execute(ins)
        logging.info("Created user-company mapping for '%s' and '%s'.", user_email, company_id)

    def update_last_sync_time(self, user_email, company_id):
        """
        Update the last_sync_time column in the user_companies table for the given user and company.
        """
        now = datetime.datetime.now(IST)
        stmt = update(self.user_companies_table).where(
            self.user_companies_table.c.user_email == user_email,
            self.user_companies_table.c.company_id == company_id
        ).values(last_sync_time=now)
        with self.engine.begin() as connection:
            connection.execute(stmt)
        logging.info("Updated last_sync_time for user '%s' and company '%s'.", user_email, company_id)

    def upload_ledgers(self, username, company_name, ledgers):
        """
        Insert ledger data into the centralized ledgers table for the specified company.
        """
        try:
            company_id = self.get_or_create_company(username, company_name)
            self.add_user_company_mapping(username, company_id, role='admin')
            with self.engine.begin() as connection:
                for ledger in ledgers:
                    # Map standard fields
                    ledger_name = ledger.get("Name", ledger.get("LEDGERNAME", "N/A"))
                    closing_balance = ledger.get("ClosingBalance", ledger.get("CLOSINGBALANCE", "N/A"))
                    
                    # Collect any additional/dynamic fields
                    standard_keys = {"Name", "LEDGERNAME", "ClosingBalance", "CLOSINGBALANCE"}
                    extra_fields = {k: v for k, v in ledger.items() if k not in standard_keys}
                    
                    ins = self.ledger_table.insert().values(
                        company_id=company_id,
                        description=ledger_name,
                        closing_balance=closing_balance,
                        timestamp=datetime.datetime.now(IST),
                        extra_data=extra_fields  # Save extra dynamic fields here
                    )
                    connection.execute(ins)
                self.update_last_sync_time(username, company_id)
            logging.info("Uploaded %d ledger records for user '%s' and company '%s' into ledgers table.", len(ledgers), username, company_name)
        except SQLAlchemyError as e:
            logging.error("Database insertion error: %s", e)

    def get_company_name_by_id(self, company_id):
        """Fetch the exact company name from companies table given the company_id."""
        stmt = select(self.companies_table.c.company_name).where(
            self.companies_table.c.company_id == company_id
        )
        with self.engine.connect() as connection:
            result = connection.execute(stmt).fetchone()
        return result[0] if result else None
    
    def get_companies_for_user(self, user_email):
        """
        Fetches a list of company names associated with the given user.
        """
        stmt = (
            select(self.companies_table.c.company_name)
            .select_from(
                self.companies_table.join(
                    self.user_companies_table,
                    self.companies_table.c.company_id == self.user_companies_table.c.company_id
                )
            )
            .where(self.user_companies_table.c.user_email == user_email)
        )
        with self.engine.connect() as connection:
            results = connection.execute(stmt).fetchall()
        # Return a list of company names
        return [row[0] for row in results]
    
    def get_last_sync_time(self, user_email, company_id):
        stmt = select(self.user_companies_table.c.last_sync_time).where(
            self.user_companies_table.c.user_email == user_email,
            self.user_companies_table.c.company_id == company_id
        )
        with self.engine.connect() as connection:
            result = connection.execute(stmt).fetchone()
        if result and result[0]:
            return result[0].strftime("%Y-%m-%d %H:%M:%S")
        return None


