# main.py
import sys
import subprocess
import time
import logging
import os
from PyQt6.QtWidgets import QApplication
from gui.main_window import MainWindow
from backend.tally_api import TallyAPI
from backend.db_connector import AwsDbConnector
from backend.cognito_auth import CognitoAuth
from backend.config import COGNITO_USER_POOL_ID, COGNITO_CLIENT_ID, COGNITO_REGION

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    try:
        logger.info("Starting Flask Server...")
        # Get the absolute path to the project directory
        project_dir = os.path.dirname(os.path.abspath(__file__))
        flask_script = os.path.join(project_dir, "services", "flask_server.py")
        
        # Start Flask server with proper environment
        flask_process = subprocess.Popen(
            [sys.executable, flask_script],
            cwd=project_dir,
            env={**os.environ, 'PYTHONPATH': project_dir}
        )
        
        # Wait for the server to be ready
        time.sleep(2)
        
        # Initialize dependencies
        try:
            db_connector = AwsDbConnector()
            tally_api = TallyAPI()
            cognito_auth = CognitoAuth(COGNITO_USER_POOL_ID, COGNITO_CLIENT_ID, COGNITO_REGION)
        except Exception as e:
            logger.error(f"Failed to initialize dependencies: {e}")
            raise
        
        # Initialize the main application
        app = QApplication(sys.argv)
        window = MainWindow(tally_api, db_connector, cognito_auth)
        window.show()
        
        # Start the event loop
        sys.exit(app.exec())
        
    except Exception as e:
        logger.error(f"Error starting application: {e}")
        sys.exit(1)
    finally:
        # Ensure Flask process is terminated
        if 'flask_process' in locals():
            flask_process.terminate()
            flask_process.wait()

if __name__ == "__main__":
    main()
