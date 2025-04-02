#!/usr/bin/env python
import os
import re
import shutil
from pathlib import Path

def update_workflow_file():
    """
    Update the GitHub workflow file with fixes we've identified
    during local testing.
    """
    workflow_file = Path('../.github/workflows/test-build.yml')
    
    if not workflow_file.exists():
        print(f"Error: Workflow file not found at {workflow_file}")
        return False
    
    # Backup the original file
    backup_file = workflow_file.with_suffix('.yml.bak')
    shutil.copy(workflow_file, backup_file)
    print(f"Backup created at {backup_file}")
    
    # Read the current workflow file
    with open(workflow_file, 'r') as f:
        content = f.read()
    
    # Update the workflow content
    updated_content = content
    
    # Add our runtime hook
    runtime_hook_content = """        # Create runtime hook
      run: |
        echo '''
import os
import sys
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('runtime_hook')

def setup_environment():
    logger.info("Setting up application environment...")
    
    if hasattr(sys, '_MEIPASS'):
        base_dir = sys._MEIPASS
        logger.info(f"Running from PyInstaller bundle at {base_dir}")
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        logger.info(f"Running as Python script from {base_dir}")
    
    os.chdir(base_dir)
    
    if base_dir not in sys.path:
        sys.path.insert(0, base_dir)
    
    for dir_name in ['data', 'templates', 'static']:
        dir_path = os.path.join(base_dir, dir_name)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
            logger.info(f"Created directory: {dir_path}")
    
    logger.info("Environment setup complete")

def fix_boto_data():
    if not hasattr(sys, '_MEIPASS'):
        return
    
    meipass_dir = sys._MEIPASS
    logger.info(f"Checking boto3/botocore data in {meipass_dir}")
    
    data_dirs = [
        ('boto3', 'data'),
        ('botocore', 'data'),
        ('botocore', 'data', 'endpoints'),
        ('botocore', 'data', 'models')
    ]
    
    for parts in data_dirs:
        dir_path = os.path.join(meipass_dir, *parts)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
            logger.info(f"Created directory: {dir_path}")

def suppress_websocket_warnings():
    try:
        from services.websocket_server import WebSocketServer
        
        original_connect = WebSocketServer.connect
        original_disconnect = WebSocketServer.disconnect
        original_send = WebSocketServer.send
        
        def patched_connect(self):
            try:
                return original_connect(self)
            except Exception:
                return False
                
        def patched_disconnect(self):
            try:
                return original_disconnect(self)
            except Exception:
                return False
                
        def patched_send(self, data):
            try:
                return original_send(self, data)
            except Exception:
                return False
        
        WebSocketServer.connect = patched_connect
        WebSocketServer.disconnect = patched_disconnect
        WebSocketServer.send = patched_send
        
        logger.info("WebSocket warnings suppressed")
    except ImportError:
        logger.warning("Could not patch WebSocket class")

logger.info("Runtime hook starting")
setup_environment()
fix_boto_data()
suppress_websocket_warnings()
logger.info("Runtime hook completed")
        ''' > runtime_hook.py
        """
    
    # Update the PyInstaller spec file
    spec_file_pattern = re.compile(r'(name: Create PyInstaller spec file\n\s+run:\s+\|\n\s+echo ")(.+?)(" > TallyfyAI.spec)', re.DOTALL)
    
    new_spec_content = """# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('.env', '.'),
        ('local_storage.db', '.'),
        ('data', 'data'),
        ('templates', 'templates'),
        ('static', 'static')
    ],
    hiddenimports=[
        'gui', 'gui.login_widget', 'gui.ledger_widget', 'gui.main_window', 'gui.user_icon', 
        'backend', 'backend.cognito_auth', 'backend.config', 'backend.db_connector', 
        'backend.tally_api', 'backend.local_db_connector', 'backend.hardware', 
        'services', 'services.flask_server', 'services.websocket_server',
        'utils', 'utils.logging_config',
        'PyQt5', 'PyQt5.QtCore', 'PyQt5.QtWidgets', 'PyQt5.QtGui',
        'flask', 'flask.json', 'werkzeug', 'jinja2', 'itsdangerous',
        'boto3', 'botocore', 'psycopg2', 'sqlalchemy', 'requests'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['runtime_hook.py'],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Add boto3/botocore data files explicitly
import os
import sys
boto3_datas = []
boto_path = None

for path in sys.path:
    if os.path.exists(os.path.join(path, 'boto3')):
        boto_path = path
        break

if boto_path:
    for root, dirs, files in os.walk(os.path.join(boto_path, 'boto3')):
        for file in files:
            if file.endswith('.json'):
                source = os.path.join(root, file)
                target = os.path.relpath(os.path.join(root, file), boto_path)
                boto3_datas.append((source, os.path.dirname(target)))
                
    for root, dirs, files in os.walk(os.path.join(boto_path, 'botocore')):
        for file in files:
            if file.endswith('.json'):
                source = os.path.join(root, file)
                target = os.path.relpath(os.path.join(root, file), boto_path)
                boto3_datas.append((source, os.path.dirname(target)))

# Add boto3/botocore data files to Analysis
a.datas.extend(boto3_datas)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='TallyfyAI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Keep console for debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='TallyfyAI',
)"""
    
    # Apply the updates
    if 'runtime_hook.py' not in updated_content:
        # Add runtime hook file creation step
        updated_content = updated_content.replace('    - name: Create PyInstaller spec file', f'    - name: Create runtime hook\n{runtime_hook_content}\n    - name: Create PyInstaller spec file')
    
    updated_content = spec_file_pattern.sub(r'\1' + new_spec_content.replace('\\', '\\\\').replace('"', '\\"').replace('$', '\\$') + r'\3', updated_content)
    
    # Write the updated workflow file
    with open(workflow_file, 'w') as f:
        f.write(updated_content)
    
    print(f"Updated workflow file: {workflow_file}")
    return True

if __name__ == "__main__":
    update_workflow_file() 