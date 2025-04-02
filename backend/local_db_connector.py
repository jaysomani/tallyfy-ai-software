import datetime
import logging
import uuid
import queue
import threading
from sqlalchemy import create_engine, Table, Column, Integer, String, MetaData, DateTime, JSON, Numeric, select, update, func
from sqlalchemy.exc import SQLAlchemyError

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Define IST timezone (UTC+5:30)
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

class LocalDbConnector:
    def __init__(self, db_path="local_storage.db"):
        # For SQLite, we add a timeout and disable the check for same thread.
        self.engine = create_engine(
            f"sqlite:///{db_path}",
            echo=False,
            future=True,
            connect_args={"timeout": 30, "check_same_thread": False}
        )
        self.metadata = MetaData()
        self.define_tables()
        self.metadata.create_all(self.engine)
        logging.info("Local SQLite database initialized and tables created if not present.")
        
        # Setup write queue and worker thread for serializing write operations.
        self.write_queue = queue.Queue()
        self.worker_thread = threading.Thread(target=self._process_queue, daemon=True)
        self.worker_thread.start()

    def define_tables(self):
        # Users Table
        self.users_table = Table(
            'users', self.metadata,
            Column('id', Integer, primary_key=True, autoincrement=True),
            Column('cognitoid', String, nullable=False),
            Column('username', String, nullable=False),
            Column('email', String, nullable=False, unique=True),
            Column('createdAt', DateTime, default=lambda: datetime.datetime.now(IST)),
            Column('updatedAt', DateTime, default=lambda: datetime.datetime.now(IST),
                   onupdate=lambda: datetime.datetime.now(IST))
        )

        # Companies Table
        self.companies_table = Table(
            'companies', self.metadata,
            Column('company_id', String, primary_key=True),
            Column('company_name', String(255), nullable=False),
            Column('created_by', String(255), nullable=False),
            Column('created_at', DateTime, default=lambda: datetime.datetime.now(IST))
        )

        # User-companies mapping Table (with last_sync_time column)
        self.user_companies_table = Table(
            'user_companies', self.metadata,
            Column('id', Integer, primary_key=True, autoincrement=True),
            Column('user_email', String(255), nullable=False),
            Column('company_id', String, nullable=False),
            Column('role', String(50), nullable=True),
            Column('last_sync_time', DateTime)
        )

        # Ledgers Table
        self.ledgers_table = Table(
            'ledgers', self.metadata,
            Column('ledger_id', Integer, primary_key=True, autoincrement=True),
            Column('company_id', String, nullable=False),
            Column('description', String(255), nullable=False),
            Column('closing_balance', Numeric, nullable=False),
            Column('timestamp', DateTime, default=lambda: datetime.datetime.now(IST)),
            Column('extra_data', JSON, nullable=True)
        )

        # Licenses Table
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

        # Temporary_transactions Table
        self.temporary_transactions = Table(
            'temporary_transactions', self.metadata,
            Column('id', Integer, primary_key=True, autoincrement=True),
            Column('upload_id', String, nullable=False),
            Column('email', String, nullable=False),
            Column('company', String, nullable=False),
            Column('bank_account', String, nullable=False),
            Column('transaction_date', DateTime, nullable=True),
            Column('transaction_type', String, nullable=True),
            Column('description', String, nullable=False),
            Column('amount', Numeric, nullable=True),
            Column('assigned_ledger', String, nullable=True, default=""),
            Column('status', String, nullable=True, default="")
        )

        # user_temp_tables Table
        self.user_temp_tables = Table(
            'user_temp_tables', self.metadata,
            Column('id', Integer, primary_key=True, autoincrement=True),
            Column('email', String, nullable=False),
            Column('company', String, nullable=False),
            Column('temp_table', String, nullable=False),
            Column('uploaded_file', String, nullable=False)
        )

    # --- Write Queue & Worker Thread Methods ---

    def _process_queue(self):
        """Worker thread function to process queued write operations sequentially."""
        while True:
            func, args, kwargs, result_queue = self.write_queue.get()
            try:
                result = func(*args, **kwargs)
                result_queue.put(result)
            except Exception as e:
                result_queue.put(e)
            finally:
                self.write_queue.task_done()

    def enqueue_write(self, func, *args, **kwargs):
        """Enqueue a write operation and wait for its result."""
        result_queue = queue.Queue()
        self.write_queue.put((func, args, kwargs, result_queue))
        return result_queue.get()

    # --- Write Operations Wrapped via the Queue ---

    def _update_last_sync_time(self, user_email, company_id):
        now = datetime.datetime.now(IST)
        stmt = update(self.user_companies_table).where(
            self.user_companies_table.c.user_email == user_email,
            self.user_companies_table.c.company_id == company_id
        ).values(last_sync_time=now)
        with self.engine.begin() as connection:
            connection.execute(stmt)
        logging.info("Updated last_sync_time for user '%s' and company '%s' in local DB.", user_email, company_id)

    def update_last_sync_time(self, user_email, company_id):
        # Enqueue the update_last_sync_time operation
        return self.enqueue_write(self._update_last_sync_time, user_email, company_id)

    def _upload_ledger(self, connection, company_id, ledger_name, closing_balance, extra_fields):
        ins = self.ledgers_table.insert().values(
            company_id=company_id,
            description=ledger_name,
            closing_balance=closing_balance,
            timestamp=datetime.datetime.now(IST),
            extra_data=extra_fields
        )
        connection.execute(ins)

    # --- Existing Methods (Reads remain unchanged) ---

    def create_user_if_not_exists(self, user_email):
        stmt = select(self.users_table.c.email).where(self.users_table.c.email == user_email)
        with self.engine.connect() as connection:
            result = connection.execute(stmt).fetchone()
        if not result:
            ins = self.users_table.insert().values(
                email=user_email,
                username=user_email,
                cognitoid=user_email,
                password="test"
            )
            # For writes, you might want to also enqueue this.
            with self.engine.begin() as connection:
                connection.execute(ins)
            logging.info("Created new user record for %s", user_email)

    def update_detected_hardware(self, user_email, new_hwid):
        now = datetime.datetime.now(IST)
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
        now = datetime.datetime.now(IST)
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
        stmt = select(self.licenses_table.c.hardwareId, self.licenses_table.c.detectedhardwareid).where(
            self.licenses_table.c.userId == user_email
        )
        with self.engine.connect() as connection:
            result = connection.execute(stmt).fetchone()
        if result:
            return result[0], result[1]
        return None, None

    def create_license_record(self, user_email, hardware_id):
        now = datetime.datetime.now(IST)
        ins = self.licenses_table.insert().values(
            licenseKey="default_key",
            userId=user_email,
            validTill=now + datetime.timedelta(days=365),
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
        company_id = company_name.replace(" ", "_").lower()
        with self.engine.connect() as connection:
            stmt = select(self.companies_table.c.company_id).where(
                self.companies_table.c.company_id == company_id
            )
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

    def upload_ledgers(self, username, company_name, ledgers):
        try:
            company_id = self.get_or_create_company(username, company_name)
            self.add_user_company_mapping(username, company_id, role='admin')
            with self.engine.begin() as connection:
                for ledger in ledgers:
                    ledger_name = ledger.get("Name", ledger.get("LEDGERNAME", "N/A"))
                    closing_balance_raw = ledger.get("ClosingBalance", ledger.get("CLOSINGBALANCE", "0"))
                    try:
                        closing_balance = float(closing_balance_raw)
                    except (ValueError, TypeError):
                        closing_balance = 0.0
                    standard_keys = {"Name", "LEDGERNAME", "ClosingBalance", "CLOSINGBALANCE"}
                    extra_fields = {k: v for k, v in ledger.items() if k not in standard_keys}

                    # Check if ledger exists.
                    select_stmt = select(self.ledgers_table.c.ledger_id).where(
                        self.ledgers_table.c.company_id == company_id,
                        self.ledgers_table.c.description == ledger_name
                    )
                    existing_ledger = connection.execute(select_stmt).fetchone()
                    if existing_ledger:
                        logging.info("Ledger '%s' already exists for company '%s'. Skipping insert.", ledger_name, company_name)
                        continue
                    # Use the internal method to insert the ledger.
                    self._upload_ledger(connection, company_id, ledger_name, closing_balance, extra_fields)
                # Enqueue updating the last sync time so that it happens sequentially.
                    self.update_last_sync_time(username, company_id)
            logging.info("Uploaded %d ledger records for user '%s' and company '%s' into local ledgers table.", len(ledgers), username, company_name)
        except SQLAlchemyError as e:
            logging.error("Local DB insertion error: %s", e)

    def get_user_companies(self, user_email):
        with self.engine.connect() as connection:
            stmt = select(
                self.companies_table.c.company_id,
                self.companies_table.c.company_name
            ).select_from(
                self.companies_table.join(
                    self.user_companies_table,
                    self.companies_table.c.company_id == self.user_companies_table.c.company_id
                )
            ).where(self.user_companies_table.c.user_email == user_email)
            result = connection.execute(stmt).fetchall()
            companies = [{"company_id": row.company_id, "company_name": row.company_name} for row in result]
        return companies

    def get_user_bank_accounts(self, user_email, company_id):
        with self.engine.connect() as connection:
            stmt_verify = select(self.user_companies_table).where(
                self.user_companies_table.c.user_email == user_email,
                self.user_companies_table.c.company_id == company_id
            )
            if not connection.execute(stmt_verify).fetchone():
                logging.warning("User '%s' has no access to company '%s'", user_email, company_id)
                return []
            stmt = select(
                self.ledgers_table.c.description.label("bank_account")
            ).distinct().where(
                self.ledgers_table.c.company_id == company_id,
                func.json_extract(self.ledgers_table.c.extra_data, '$.PARENT') == "Bank Accounts"
            )
            result = connection.execute(stmt).fetchall()
            bank_accounts = [row.bank_account for row in result]
        return bank_accounts

    def convert_date(self, date_str):
        try:
            return datetime.datetime.fromisoformat(date_str)
        except Exception:
            try:
                return datetime.datetime.strptime(date_str, "%d/%m/%Y")
            except Exception:
                return None

    def upload_excel_local(self, email, company, bankAccount, data, fileName):
        try:
            upload_id = str(uuid.uuid4())
            with self.engine.begin() as connection:
                for row in data:
                    let_date = row.get("transaction_date") or row.get("txn_date")
                    jsDate = None
                    if let_date:
                        jsDate = self.convert_date(let_date)
                    txn_type = row.get("transaction_type") or row.get("type") or None
                    assigned_ledger = row.get("assignedLedger") or row.get("ledger") or ""
                    connection.execute(
                        self.temporary_transactions.insert().values(
                            upload_id=upload_id,
                            email=email,
                            company=company,
                            bank_account=bankAccount,
                            transaction_date=jsDate,
                            transaction_type=txn_type,
                            description=row.get("description"),
                            amount=row.get("amount"),
                            assigned_ledger=assigned_ledger
                        )
                    )
                connection.execute(
                    self.user_temp_tables.insert().values(
                        email=email,
                        company=company,
                        temp_table=upload_id,
                        uploaded_file=fileName
                    )
                )
                stmt = select(self.temporary_transactions.c.id).where(
                    self.temporary_transactions.c.upload_id == upload_id
                )
                rows = connection.execute(stmt).fetchall()
                logging.info(f"Now have {len(rows)} rows for upload {upload_id}")
            return upload_id
        except SQLAlchemyError as e:
            logging.error("Error in upload_excel_local: %s", e)
            raise e

    def get_all_temp_tables(self, email, company):
        with self.engine.connect() as connection:
            stmt = select(
                self.user_temp_tables.c.temp_table,
                self.user_temp_tables.c.uploaded_file,
            ).where(
                self.user_temp_tables.c.email == email,
                self.user_temp_tables.c.company == company
            ).order_by(self.user_temp_tables.c.id.desc())
            result = connection.execute(stmt).fetchall()
            temp_tables = [
                {
                    "temp_table": row.temp_table,
                    "uploaded_file": row.uploaded_file,
                }
                for row in result
            ]
        return temp_tables

    def get_temp_table_data(self, upload_id):
        with self.engine.connect() as conn:
            stmt = select(self.temporary_transactions).where(
                self.temporary_transactions.c.upload_id == upload_id
            )
            result = conn.execute(stmt).fetchall()
            data = [dict(row._mapping) for row in result]
            for row in data:
                for key, value in row.items():
                    from decimal import Decimal
                    if isinstance(value, Decimal):
                        row[key] = float(value)
                    elif isinstance(value, datetime.datetime):
                        row[key] = value.isoformat()
            return data

    def update_temp_excel(self, upload_id, data):
        try:
            # Enqueue the update_temp_excel write operations if desired.
            def _update_temp_excel():
                with self.engine.begin() as connection:
                    delete_stmt = self.temporary_transactions.delete().where(
                        self.temporary_transactions.c.upload_id == upload_id
                    )
                    connection.execute(delete_stmt)
                    for row in data:
                        let_date = row.get("transaction_date")
                        jsDate = self.convert_date(let_date) if let_date else None
                        txn_type = row.get("transaction_type") or row.get("type") or None
                        assigned_ledger = row.get("assignedLedger") or row.get("assigned_ledger") or ""
                        connection.execute(
                            self.temporary_transactions.insert().values(
                                upload_id=upload_id,
                                email=row.get("email", ""),
                                company=row.get("company", ""),
                                bank_account=row.get("bank_account", ""),
                                transaction_date=jsDate,
                                transaction_type=txn_type,
                                description=row.get("description", ""),
                                amount=row.get("amount", 0),
                                assigned_ledger=assigned_ledger
                            )
                        )
                logging.info(f"update_temp_excel: updated rows for upload {upload_id}")
                return upload_id

            return self.enqueue_write(_update_temp_excel)
        except SQLAlchemyError as e:
            logging.error("Error in update_temp_excel: %s", e)
            raise e

    def update_transactions_status_all(self, upload_id, new_status):
        try:
            with self.engine.begin() as connection:
                update_stmt = (
                    self.temporary_transactions.update()
                    .where(self.temporary_transactions.c.upload_id == upload_id)
                    .values(status=new_status)
                )
                connection.execute(update_stmt)
            logging.info("Updated all transactions for upload %s to status '%s'", upload_id, new_status)
        except Exception as e:
            logging.error("Error updating transactions status: %s", e)
            raise e

    def get_company_name(self, company_id):
        with self.engine.connect() as connection:
            stmt = select(self.companies_table.c.company_name).where(
                self.companies_table.c.company_id == company_id
            )
            result = connection.execute(stmt).fetchone()
            return result[0] if result else None

    def get_ledger_options(self, company_id):
        with self.engine.connect() as connection:
            stmt = select(self.ledgers_table.c.description).where(
                self.ledgers_table.c.company_id == company_id
            )
            result = connection.execute(stmt).fetchall()
            logging.info("Ledger rows found for %s: %s", company_id, result)
            ledger_options = [row[0] for row in result]
        return ledger_options

    def get_last_synced_company(self, user_email):
        from sqlalchemy import desc
        with self.engine.connect() as connection:
            stmt = (
                select(self.companies_table.c.company_name)
                .select_from(
                    self.companies_table.join(
                        self.user_companies_table,
                        self.companies_table.c.company_id == self.user_companies_table.c.company_id
                    )
                )
                .where(self.user_companies_table.c.user_email == user_email)
                .order_by(desc(self.companies_table.c.created_at))
            )
            result = connection.execute(stmt).fetchone()
            return result[0] if result else None

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