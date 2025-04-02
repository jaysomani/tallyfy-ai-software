# gui/main_window.py
import logging
import subprocess
import time

from PyQt6.QtWidgets import QMainWindow, QStackedWidget, QLabel, QMessageBox
from PyQt6.QtCore import QTimer
from PyQt6.QtWebSockets import QWebSocket
from PyQt6.QtCore import QUrl

from gui.login_widget import LoginWidget
from gui.ledger_widget import LedgerWidget
from backend.hardware import get_hardware_id  # Ensure this is in your backend module

class MainWindow(QMainWindow):
    """
    Main application window that uses a QStackedWidget to switch between the login and ledger screens.
    Also handles establishing a WebSocket connection for real-time updates.
    """
    def __init__(self, tally_api, db_connector, cognito_auth):
        super().__init__()
        self.tally_api = tally_api
        self.db_connector = db_connector
        self.cognito_auth = cognito_auth
        self.setWindowTitle("Tally Connector")
        self.resize(800, 600)
        self.stacked = QStackedWidget()
        self.setCentralWidget(self.stacked)
        
        # Status label on the status bar for WebSocket connection state.
        self.status_label = QLabel("WebSocket Status: Connecting...")
        self.statusBar().addWidget(self.status_label)
        
        # Initialize WebSocket connection.
        self.ws = None
        self.connect_websocket()
        
        # Setup the login widget.
        self.login_widget = LoginWidget(self.cognito_auth)
        self.login_widget.switch_to_main_signal.connect(self.switch_to_ledger)
        self.stacked.addWidget(self.login_widget)
    
    def connect_websocket(self):
        if self.ws:
            self.ws.close()
        self.ws = QWebSocket()
        self.ws.connected.connect(self.on_ws_connected)
        self.ws.disconnected.connect(self.on_ws_disconnected)
        self.ws.errorOccurred.connect(self.on_ws_error)
        try:
            self.ws.open(QUrl("ws://localhost:8000/"))
        except Exception as e:
            logging.error(f"Failed to open WebSocket connection: {e}")
            self.status_label.setText("WebSocket Status: Connection Failed")
    
    def on_ws_connected(self):
        self.status_label.setText("WebSocket Status: Connected")
        logging.info("WebSocket connected successfully")
    
    def on_ws_error(self, error):
        error_msg = self.ws.errorString()
        self.status_label.setText(f"WebSocket Status: Error - {error_msg}")
        logging.error("WebSocket error: %s", error_msg)
        QTimer.singleShot(5000, self.connect_websocket)
    
    def on_ws_disconnected(self):
        self.status_label.setText("WebSocket Status: Disconnected")
        logging.info("WebSocket disconnected")
        QTimer.singleShot(5000, self.connect_websocket)
    
    def switch_to_ledger(self, username, user_type):
        # For silver users, verify hardware binding.
        if user_type == "silver":
            current_hwid = get_hardware_id()
            self.db_connector.create_user_if_not_exists(username)
            registered_hwid, detected_hwid = self.db_connector.get_license_hardware(username)
            if not registered_hwid or registered_hwid.strip() == "":
                self.db_connector.create_license_record(username, current_hwid)
            elif registered_hwid != current_hwid:
                self.db_connector.update_detected_hardware(username, current_hwid)
                QMessageBox.critical(
                    self,
                    "Hardware Mismatch",
                    ("Your current hardware does not match the registered machine. "
                     "The new hardware has been recorded. Please contact support to shift your license.")
                )
                self.switch_to_login()
                return
        
        # Create the LedgerWidget and switch the stacked widget view.
        self.ledger_widget = LedgerWidget(username, self.tally_api, self.db_connector, user_type)
        self.ledger_widget.logout_btn.clicked.connect(self.switch_to_login)
        self.stacked.addWidget(self.ledger_widget)
        self.stacked.setCurrentWidget(self.ledger_widget)
    
    def switch_to_login(self):
        self.stacked.setCurrentWidget(self.login_widget)
    
    def closeEvent(self, event):
        if self.ws:
            self.ws.close()
        super().closeEvent(event)
