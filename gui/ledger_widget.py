import datetime
import os
import threading
import logging
import webbrowser

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox,
    QFrame, QScrollArea, QSpacerItem, QSizePolicy, QStyle
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import QTimer, pyqtSignal, Qt

from backend.db_connector import IST

# Define website URLs (or use os.getenv in production)
LIVE_WEBSITE_URL = os.getenv("LIVE_WEBSITE_URL", "https://live.example.com")
LOCAL_WEBSITE_URL = os.getenv("LOCAL_WEBSITE_URL", "http://localhost:9000")

class LedgerWidget(QWidget):
    """
    A dark-themed LedgerWidget. The active company is displayed at the top with a refresh icon for syncing ledger data.
    Once data is synced (for gold or silver users), the last sync time (in IST) is fetched from the corresponding database
    and displayed.
    Gold users are prompted to visit the live website after syncing.
    """
    ledgers_fetched = pyqtSignal(str, list)
    
    def __init__(self, username, tally_api, db_connector, user_type):
        super().__init__()
        self.username = username
        self.user_type = user_type.lower()  # 'gold', 'silver', or 'trial'
        self.tally_api = tally_api
        self.db_connector = db_connector

        # For silver users, initialize the local DB connector.
        if self.user_type == "silver":
            from backend.local_db_connector import LocalDbConnector
            self.local_db_connector = LocalDbConnector()

        self.ledgers = []
        self.active_company = "Loading..."
        self.stored_companies = []
        self.last_sync_time = None

        self.setup_ui()
        self.ledgers_fetched.connect(self.on_ledgers_fetched)
        
        # Fetch initial data
        self.fetch_active_company()
        QTimer.singleShot(0, self.fetch_stored_company)
        QTimer.singleShot(0, lambda: self.update_ledgers(sync_data=False))
    
    def setup_ui(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                color: #eeeeee;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 14px;
            }
            QPushButton {
                background-color: #007acc;
                color: #ffffff;
                border: 1px solid #007acc;
                border-radius: 5px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #005fa3;
            }
            QLabel {
                color: #cccccc;
            }
            QScrollArea {
                border: none;
            }
            QFrame#ActiveCompanyFrame {
                background-color: #2b2d2f;
                border: 1px solid #555;
                border-radius: 10px;
                padding: 15px;
            }
            QFrame#CompanyItemFrame {
                background-color: #2f2f2f;
                border: 1px solid #444;
                border-radius: 5px;
                padding: 8px;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)
        
        # Top Bar
        top_bar = QHBoxLayout()
        title = QLabel("Tally Connector")
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffffff;")
        top_bar.addWidget(title)
        top_bar.addStretch()

        self.user_type_label = QLabel(self.user_type.upper())
        self.user_type_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        if self.user_type == "gold":
            self.user_type_label.setStyleSheet("color: #00c851;")
        else:
            self.user_type_label.setStyleSheet("color: #33b5e5;")
        top_bar.addWidget(self.user_type_label)

        refresh_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload)
        self.refresh_icon_btn = QPushButton()
        self.refresh_icon_btn.setIcon(refresh_icon)
        self.refresh_icon_btn.setToolTip("Refresh Active Company")
        self.refresh_icon_btn.clicked.connect(self.fetch_active_company)
        self.refresh_icon_btn.setFixedSize(32, 32)
        top_bar.addWidget(self.refresh_icon_btn)

        from gui.user_icon import UserIcon
        self.user_icon = UserIcon(self.username)
        self.user_icon.mousePressEvent = self.open_profile
        top_bar.addWidget(self.user_icon)

        main_layout.addLayout(top_bar)
        
        # Scroll Area for Companies
        self.company_scroll = QScrollArea()
        self.company_scroll.setWidgetResizable(True)
        self.company_container = QWidget()
        self.company_layout = QVBoxLayout(self.company_container)
        self.company_container.setLayout(self.company_layout)
        self.company_scroll.setWidget(self.company_container)
        main_layout.addWidget(self.company_scroll)
        
        # Bottom Bar (Logout Only)
        btn_layout = QHBoxLayout()
        self.logout_btn = QPushButton("Logout")
        btn_layout.addWidget(self.logout_btn)
        main_layout.addLayout(btn_layout)

    def update_company_list_ui(self):
        logging.info("Updating company list UI.")
        while self.company_layout.count():
            child = self.company_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Active Company Section (Horizontal layout with last sync time before sync button)
        active_frame = QFrame(objectName="ActiveCompanyFrame")
        active_layout = QHBoxLayout(active_frame)
        
        active_label = QLabel(f"Active Company: {self.active_company}")
        active_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        active_label.setStyleSheet("color: #00e676;")
        active_layout.addWidget(active_label)
        
        # Last Sync Time Label (if available)
        if self.last_sync_time:
            last_sync_label = QLabel(f"Last Sync: {self.last_sync_time}")
            last_sync_label.setFont(QFont("Segoe UI", 12))
            last_sync_label.setStyleSheet("color: #bbbbbb; margin-left: 10px;")
            active_layout.addWidget(last_sync_label)
        
        active_layout.addStretch()
        
        ledger_refresh_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload)
        self.ledger_refresh_btn = QPushButton()
        self.ledger_refresh_btn.setIcon(ledger_refresh_icon)
        self.ledger_refresh_btn.setToolTip("Refresh Ledger & Store Data")
        self.ledger_refresh_btn.clicked.connect(lambda: self.update_ledgers(sync_data=True))
        self.ledger_refresh_btn.setFixedSize(32, 32)
        active_layout.addWidget(self.ledger_refresh_btn)
        
        self.company_layout.addWidget(active_frame)
        
        # Separator Line
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setStyleSheet("color: #666; margin: 10px 0;")
        self.company_layout.addWidget(separator)
        
        # Stored Companies Section
        for company in self.stored_companies:
            # company = company["company_name"]
            if company.strip().lower() == self.active_company.strip().lower():
                continue
            comp_frame = QFrame(objectName="CompanyItemFrame")
            comp_layout = QHBoxLayout(comp_frame)
            comp_label = QLabel(company.strip())
            comp_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Medium))
            comp_label.setStyleSheet("color: #ff4444;")
            comp_layout.addWidget(comp_label)
            self.company_layout.addWidget(comp_frame)
        
        self.company_layout.addSpacerItem(QSpacerItem(
            20, 40,
            QSizePolicy.Policy.Minimum,
            QSizePolicy.Policy.Expanding
        ))
        
        self.company_container.adjustSize()
        self.company_container.update()
        self.company_scroll.viewport().update()
        logging.info("Company list UI updated.")

    def fetch_active_company(self):
        def fetch():
            if not self.tally_api.is_tally_running():
                self.active_company = "Tally not running"
            else:
                self.active_company = self.tally_api.get_active_company(use_cache=False)
            # For both gold and silver users, use the appropriate DB connector to get company_id and then last sync time.
            if self.user_type == "gold":
                company_id = self.db_connector.get_or_create_company(self.username, self.active_company)
                self.last_sync_time = self.db_connector.get_last_sync_time(self.username, company_id)
            elif self.user_type == "silver":
                company_id = self.local_db_connector.get_or_create_company(self.username, self.active_company)
                self.last_sync_time = self.local_db_connector.get_last_sync_time(self.username, company_id)
            QTimer.singleShot(0, self.update_company_list_ui)
        threading.Thread(target=fetch, daemon=True).start()
    
    def fetch_stored_company(self):
        def fetch():
            if self.user_type == "silver":
                dict_companies = self.local_db_connector.get_user_companies(self.username)
                # Convert them to a list of strings:
                companies = [d["company_name"] for d in dict_companies]
                logging.info("Local DB - companies list: %s", companies)
            else:
                companies = self.db_connector.get_companies_for_user(self.username)
                logging.info("AWS DB - companies list: %s", companies)
            
            if not companies:
                companies = ["None"]
            
            self.stored_companies = companies
            logging.info("Final companies list: %s", companies)
            QTimer.singleShot(0, self.update_company_list_ui)
        threading.Thread(target=fetch, daemon=True).start()

    def update_ledgers(self, sync_data=True):
        def fetch_data():
            if not self.tally_api.is_tally_running():
                self.ledgers_fetched.emit("Tally not running", [])
                return
            active = self.tally_api.get_active_company()
            fetch_fields = ["LEDGERNAME", "PARENT", "CLOSINGBALANCE"]
            ledgers = self.tally_api.fetch_data(
                request_id="AllLedgers",
                collection_type="Ledger",
                fetch_fields=fetch_fields,
                use_cache=False
            )
            self.ledgers = ledgers
            self.ledgers_fetched.emit(active, ledgers)

            if sync_data:
                if self.user_type == "gold":
                    company_id = self.db_connector.get_or_create_company(self.username, active)
                    self.db_connector.upload_ledgers(self.username, active, ledgers)
                    QTimer.singleShot(0, self.show_live_website_popup)
                    self.last_sync_time = self.db_connector.get_last_sync_time(self.username, company_id)
                elif self.user_type == "silver":
                    company_id = self.local_db_connector.get_or_create_company(self.username, active)
                    self.local_db_connector.upload_ledgers(self.username, active, ledgers)
                    QTimer.singleShot(0, self.show_local_website_popup)
                    self.last_sync_time = self.local_db_connector.get_last_sync_time(self.username, company_id)
                elif self.user_type == "trial":
                    allowed_company = self.username
                    if active != allowed_company:
                        QMessageBox.warning(
                            self,
                            "Trial Limit",
                            f"Trial accounts are limited to syncing data for '{allowed_company}'."
                        )
                    else:
                        self.db_connector.upload_ledgers(self.username, active, ledgers)
                    self.last_sync_time = datetime.datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
                QTimer.singleShot(0, self.fetch_stored_company)
                QTimer.singleShot(0, self.update_company_list_ui)
        threading.Thread(target=fetch_data, daemon=True).start()
    
    def show_local_website_popup(self):
        reply = QMessageBox.question(
            self,
            "Local Website",
            "Data stored locally. Do you want to visit your local website?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            webbrowser.open(LOCAL_WEBSITE_URL)

    def show_live_website_popup(self):
        reply = QMessageBox.question(
            self,
            "Live Website",
            "Data stored in the cloud. Do you want to visit our live website?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            webbrowser.open(LIVE_WEBSITE_URL)

    def sync_data(self):
        self.show_live_website_popup()
    
    def on_ledgers_fetched(self, active_company, ledgers):
        self.active_company = active_company
        self.update_company_list_ui()
    
    def open_profile(self, event):
        QMessageBox.information(self, "Profile", f"Username: {self.username}\n(Additional profile info here)")
