"""
PyInstaller runtime hook for Tallyfy.ai application
This script runs at application startup to fix common issues with PyInstaller packaging
"""

import os
import sys
import shutil
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('runtime_hook')

def setup_environment():
    """Set up the environment for the application"""
    logger.info("Setting up application environment...")
    
    # Get the directory where the executable is located
    if hasattr(sys, '_MEIPASS'):
        # Running as a PyInstaller bundle
        base_dir = sys._MEIPASS
        logger.info(f"Running from PyInstaller bundle at {base_dir}")
    else:
        # Running as a Python script
        base_dir = os.path.dirname(os.path.abspath(__file__))
        logger.info(f"Running as Python script from {base_dir}")
    
    # Set current directory to the base directory
    os.chdir(base_dir)
    
    # Add the base directory to the Python path
    if base_dir not in sys.path:
        sys.path.insert(0, base_dir)
    
    # Create necessary directories if they don't exist
    for dir_name in ['data', 'templates', 'static']:
        dir_path = os.path.join(base_dir, dir_name)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
            logger.info(f"Created directory: {dir_path}")
    
    # Create .env file if it doesn't exist
    env_path = os.path.join(base_dir, '.env')
    if not os.path.exists(env_path):
        logger.info(f"Creating .env file at {env_path}")
        with open(env_path, 'w') as f:
            f.write("""AWS_DB_URL=postgresql://dummy:dummy@localhost:5432/dummy
TALLY_URL=http://localhost:9000
COGNITO_USER_POOL_ID=us-east-1_dummy
COGNITO_CLIENT_ID=dummyclientid
COGNITO_REGION=us-east-1
TESTING=true
""")
    
    # Create local_storage.db if it doesn't exist
    db_path = os.path.join(base_dir, 'local_storage.db')
    if not os.path.exists(db_path):
        logger.info(f"Creating empty local_storage.db at {db_path}")
        with open(db_path, 'w') as f:
            pass
    
    # Fix boto3/botocore data
    fix_boto_data()
    
    logger.info("Environment setup complete")

def fix_boto_data():
    """Fix missing boto3/botocore data files"""
    if not hasattr(sys, '_MEIPASS'):
        # Not running in PyInstaller environment
        return
    
    meipass_dir = sys._MEIPASS
    logger.info(f"Checking boto3/botocore data in {meipass_dir}")
    
    # Fix potential missing boto3/botocore data directories
    data_dirs = [
        ('boto3', 'data'),
        ('botocore', 'data'),
        ('botocore', 'data', 'endpoints'),
        ('botocore', 'data', 'models'),
        ('botocore', 'data', 'iam')
    ]
    
    for parts in data_dirs:
        dir_path = os.path.join(meipass_dir, *parts)
        if not os.path.exists(dir_path):
            logger.warning(f"Directory missing: {dir_path}")
            os.makedirs(dir_path, exist_ok=True)
            logger.info(f"Created directory: {dir_path}")

def suppress_websocket_warnings():
    """Suppress WebSocket related warnings and errors"""
    # Patch the WebSocket class to avoid excessive error messages
    try:
        from services.websocket_server import WebSocketServer
        
        original_connect = WebSocketServer.connect
        original_disconnect = WebSocketServer.disconnect
        original_send = WebSocketServer.send
        
        def patched_connect(self):
            try:
                return original_connect(self)
            except Exception as e:
                # Suppress the exception but log it once
                if not hasattr(self, '_connect_error_logged'):
                    logger.debug(f"WebSocket connect suppressed: {str(e)}")
                    self._connect_error_logged = True
                return False
                
        def patched_disconnect(self):
            try:
                return original_disconnect(self)
            except Exception as e:
                # Suppress the exception
                return False
                
        def patched_send(self, data):
            try:
                return original_send(self, data)
            except Exception as e:
                # Suppress the exception but log it once
                if not hasattr(self, '_send_error_logged'):
                    logger.debug(f"WebSocket send suppressed: {str(e)}")
                    self._send_error_logged = True
                return False
        
        WebSocketServer.connect = patched_connect
        WebSocketServer.disconnect = patched_disconnect
        WebSocketServer.send = patched_send
        
        logger.info("WebSocket warnings suppressed")
    except ImportError:
        logger.warning("Could not patch WebSocket class (not imported yet)")

# Run the setup
logger.info("Runtime hook starting")
setup_environment()
suppress_websocket_warnings()
logger.info("Runtime hook completed") 