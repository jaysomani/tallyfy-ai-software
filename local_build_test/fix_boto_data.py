import os
import sys
import shutil
from pathlib import Path

def fix_boto_data_files():
    """
    Fix missing boto3/botocore data files in PyInstaller build
    
    This function copies all boto3 and botocore data files to the 
    temporary directory created by PyInstaller during runtime
    """
    print("Fixing boto3/botocore data files...")
    
    # Find the location of the boto3 package
    boto3_path = None
    botocore_path = None
    
    for path in sys.path:
        if os.path.exists(os.path.join(path, 'boto3')):
            boto3_path = os.path.join(path, 'boto3')
        if os.path.exists(os.path.join(path, 'botocore')):
            botocore_path = os.path.join(path, 'botocore')
        if boto3_path and botocore_path:
            break
    
    if not boto3_path or not botocore_path:
        print("Error: Could not find boto3 or botocore packages")
        return False
    
    # Get the temp directory created by PyInstaller
    if hasattr(sys, '_MEIPASS'):
        meipass_dir = sys._MEIPASS
    else:
        print("Warning: Not running in PyInstaller environment")
        return False
    
    # Copy boto3 data files
    source_boto3_data = os.path.join(boto3_path, 'data')
    target_boto3_data = os.path.join(meipass_dir, 'boto3', 'data')
    
    if os.path.exists(source_boto3_data):
        print(f"Copying boto3 data from {source_boto3_data} to {target_boto3_data}")
        if not os.path.exists(target_boto3_data):
            os.makedirs(os.path.dirname(target_boto3_data), exist_ok=True)
        shutil.copytree(source_boto3_data, target_boto3_data, dirs_exist_ok=True)
    
    # Copy botocore data files
    source_botocore_data = os.path.join(botocore_path, 'data')
    target_botocore_data = os.path.join(meipass_dir, 'botocore', 'data')
    
    if os.path.exists(source_botocore_data):
        print(f"Copying botocore data from {source_botocore_data} to {target_botocore_data}")
        if not os.path.exists(target_botocore_data):
            os.makedirs(os.path.dirname(target_botocore_data), exist_ok=True)
        shutil.copytree(source_botocore_data, target_botocore_data, dirs_exist_ok=True)
    
    print("Boto3/botocore data files fixed successfully")
    return True

if __name__ == "__main__":
    fix_boto_data_files() 