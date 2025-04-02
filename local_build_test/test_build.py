#!/usr/bin/env python
import os
import sys
import shutil
import subprocess
import time
import signal
import platform
from pathlib import Path

# Colors for console output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_step(message):
    print(f"\n{Colors.HEADER}{Colors.BOLD}=== {message} ==={Colors.ENDC}\n")

def print_success(message):
    print(f"{Colors.GREEN}✓ {message}{Colors.ENDC}")

def print_error(message):
    print(f"{Colors.FAIL}✗ {message}{Colors.ENDC}")

def print_warning(message):
    print(f"{Colors.WARNING}! {message}{Colors.ENDC}")

def run_command(command, env=None):
    print(f"{Colors.BLUE}Running: {' '.join(command)}{Colors.ENDC}")
    
    # Use current environment and update with any additional variables
    current_env = os.environ.copy()
    if env:
        current_env.update(env)
    
    result = subprocess.run(command, env=current_env, capture_output=True, text=True)
    
    if result.returncode == 0:
        print_success(f"Command completed with exit code {result.returncode}")
    else:
        print_error(f"Command failed with exit code {result.returncode}")
        
    if result.stdout.strip():
        print(f"Output:\n{result.stdout.strip()}")
    if result.stderr.strip():
        print(f"Errors:\n{result.stderr.strip()}")
        
    return result

def create_necessary_files():
    print_step("Creating necessary files")
    
    # Create .env file
    with open('.env', 'w') as f:
        f.write(f"""AWS_DB_URL=postgresql://dummy:dummy@localhost:5432/dummy
TALLY_URL=http://localhost:9000
COGNITO_USER_POOL_ID=us-east-1_dummy
COGNITO_CLIENT_ID=dummyclientid
COGNITO_REGION=us-east-1
TESTING=true
""")
    print_success("Created .env file")
    
    # Create empty local_storage.db
    with open('local_storage.db', 'w') as f:
        pass
    print_success("Created local_storage.db")
    
    # Create data directory
    os.makedirs('data', exist_ok=True)
    with open('data/placeholder.txt', 'w') as f:
        f.write("Placeholder file")
    print_success("Created data directory")
    
    # Create templates and static directories
    os.makedirs('templates', exist_ok=True)
    with open('templates/index.html', 'w') as f:
        f.write("<!DOCTYPE html><html><body><h1>Placeholder</h1></body></html>")
    print_success("Created templates directory")
    
    os.makedirs('static', exist_ok=True)
    with open('static/style.css', 'w') as f:
        f.write("/* Placeholder CSS */")
    print_success("Created static directory")

def create_spec_file():
    print_step("Creating PyInstaller spec file")
    
    spec_content = """# -*- mode: python ; coding: utf-8 -*-

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
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Include all of boto3/botocore data files
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
)
"""
    
    with open('local_test.spec', 'w') as f:
        f.write(spec_content)
    
    print_success("Created PyInstaller spec file: local_test.spec")

def build_application():
    print_step("Building application with PyInstaller")
    
    # Use PyInstaller to build the application
    env_vars = {
        'AWS_DB_URL': 'postgresql://dummy:dummy@localhost:5432/dummy',
        'TALLY_URL': 'http://localhost:9000',
        'COGNITO_USER_POOL_ID': 'us-east-1_dummy',
        'COGNITO_CLIENT_ID': 'dummyclientid',
        'COGNITO_REGION': 'us-east-1',
        'TESTING': 'true'
    }
    
    # Run PyInstaller
    result = run_command(['pyinstaller', 'local_test.spec'], env=env_vars)
    
    if result.returncode != 0:
        print_error("PyInstaller build failed")
        return False
        
    print_success("PyInstaller build completed")
    return True

def check_executable():
    print_step("Checking executable")
    
    exe_path = os.path.join('dist', 'TallyfyAI', 'TallyfyAI.exe')
    
    if not os.path.exists(exe_path):
        print_error(f"Executable not found at {exe_path}")
        return False
        
    print_success(f"Executable found at {exe_path}")
    
    # Test the executable by running it
    print_warning("Starting executable for testing (it will run for 5 seconds)")
    
    try:
        # Start the executable
        process = None
        if platform.system() == 'Windows':
            # Use subprocess.Popen for Windows
            process = subprocess.Popen([exe_path], 
                                      stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE,
                                      creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            # For other platforms
            process = subprocess.Popen([exe_path],
                                      stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE)
            
        # Wait for 5 seconds to see if it crashes immediately
        time.sleep(5)
        
        # Check if the process is still running
        if process.poll() is None:
            print_success("Executable is running successfully")
            
            # Terminate the process
            if platform.system() == 'Windows':
                # On Windows, use taskkill to force close the process tree
                subprocess.run(['taskkill', '/F', '/T', '/PID', str(process.pid)], 
                              capture_output=True)
            else:
                # On other platforms, terminate the process
                process.terminate()
                process.wait(timeout=3)
                if process.poll() is None:
                    process.kill()
            
            return True
        else:
            print_error(f"Executable terminated prematurely with code {process.returncode}")
            stdout, stderr = process.communicate()
            if stdout:
                print(f"Stdout:\n{stdout.decode('utf-8', errors='ignore')}")
            if stderr:
                print(f"Stderr:\n{stderr.decode('utf-8', errors='ignore')}")
            return False
            
    except Exception as e:
        print_error(f"Error running executable: {e}")
        return False

def main():
    print_step("Starting local build test")
    
    # Check if PyInstaller is installed
    try:
        import PyInstaller
        print_success("PyInstaller is installed")
    except ImportError:
        print_error("PyInstaller is not installed. Please install it with 'pip install pyinstaller'")
        return
    
    # Create necessary files
    create_necessary_files()
    
    # Create spec file
    create_spec_file()
    
    # Build the application
    if not build_application():
        return
    
    # Check if the executable works
    if check_executable():
        print_step("TEST SUCCESSFUL")
        print_success("The application was built and ran successfully")
        print(f"{Colors.BOLD}You can find the built application in the 'dist/TallyfyAI' directory{Colors.ENDC}")
    else:
        print_step("TEST FAILED")
        print_error("The application build or execution test failed")

if __name__ == "__main__":
    main() 