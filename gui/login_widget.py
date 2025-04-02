# gui/login_widget.py
import logging
import jwt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout, QMessageBox
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, pyqtSignal

class LoginWidget(QWidget):
    switch_to_main_signal = pyqtSignal(str, str)  # Emits (username, user_type)

    def __init__(self, cognito_auth):
        super().__init__()
        self.cognito_auth = cognito_auth
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        title = QLabel("Login - Tally Connector")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("Email")
        layout.addWidget(self.username_edit)
        
        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("Password")
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.password_edit)
        
        btn_layout = QHBoxLayout()
        login_btn = QPushButton("Login")
        login_btn.clicked.connect(self.login)
        btn_layout.addWidget(login_btn)
        
        signup_btn = QPushButton("Sign Up")
        signup_btn.clicked.connect(self.signup)
        btn_layout.addWidget(signup_btn)
        
        layout.addLayout(btn_layout)

    def login(self):
        username = self.username_edit.text().strip()
        password = self.password_edit.text().strip()
        success, response = self.cognito_auth.sign_in(username, password)
        
        if success:
            try:
                id_token = response['AuthenticationResult']['IdToken']
                decoded = jwt.decode(id_token, options={"verify_signature": False})
                groups = decoded.get("cognito:groups", [])
            except Exception as e:
                logging.error("Error decoding token: %s", e)
                groups = []

            # Check if the user is assigned any group.
            if not groups:
                QMessageBox.critical(self, "Login Failed", 
                    "No valid role was assigned to your account. Please contact support.")
                return

            # Determine user role with explicit checks.
            if any("gold" == group.lower() for group in groups):
                user_type = "gold"
            elif any("trial" == group.lower() for group in groups):
                user_type = "trial"
            elif any("silver" == group.lower() for group in groups):
                user_type = "silver"
            else:
                QMessageBox.critical(self, "Login Failed", 
                    "We are not able to recognize your acct if you have purchased any of our product please contact support.")
                return

            logging.info("User %s logged in with role %s", username, user_type)
            self.switch_to_main_signal.emit(username, user_type)
        else:
            QMessageBox.critical(self, "Login Failed", "Incorrect username or password.")

    def signup(self):
        username = self.username_edit.text().strip()
        password = self.password_edit.text().strip()
        success, response = self.cognito_auth.sign_up(username, password)
        if success:
            QMessageBox.information(self, "Sign Up", "Account created. Please confirm your account via email.")
        else:
            QMessageBox.critical(self, "Sign Up Failed", "An error occurred. Try a different username.")
