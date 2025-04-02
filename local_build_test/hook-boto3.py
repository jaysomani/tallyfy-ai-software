"""
PyInstaller hook for boto3 and botocore

This ensures that all data files from boto3 and botocore are included in the package.
"""

import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Standard imports for boto3/botocore
hiddenimports = [
    'boto3',
    'botocore',
]

# Add all boto3 and botocore submodules
hiddenimports += collect_submodules('boto3')
hiddenimports += collect_submodules('botocore')

# Collect data files for boto3 and botocore
datas = collect_data_files('boto3')
datas += collect_data_files('botocore')

# Explicitly add data directories to ensure they're included
boto3_path = None
botocore_path = None

for path in sys.path:
    if os.path.exists(os.path.join(path, 'boto3')):
        boto3_path = os.path.join(path, 'boto3')
    if os.path.exists(os.path.join(path, 'botocore')):
        botocore_path = os.path.join(path, 'botocore')
    if boto3_path and botocore_path:
        break

if boto3_path:
    # Add boto3 data directory
    boto3_data_path = os.path.join(boto3_path, 'data')
    if os.path.exists(boto3_data_path):
        for root, dirs, files in os.walk(boto3_data_path):
            for file in files:
                source = os.path.join(root, file)
                target = os.path.relpath(source, os.path.dirname(boto3_path))
                datas.append((source, os.path.dirname(target)))

if botocore_path:
    # Add botocore data directory
    botocore_data_path = os.path.join(botocore_path, 'data')
    if os.path.exists(botocore_data_path):
        for root, dirs, files in os.walk(botocore_data_path):
            for file in files:
                source = os.path.join(root, file)
                target = os.path.relpath(source, os.path.dirname(botocore_path))
                datas.append((source, os.path.dirname(target)))

    # Add botocore cacert.pem
    cacert_path = os.path.join(botocore_path, 'cacert.pem')
    if os.path.exists(cacert_path):
        datas.append((cacert_path, 'botocore')) 