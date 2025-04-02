# Local Build Test for Tallyfy.ai

This folder contains scripts to test building and packaging the Tallyfy.ai application locally before pushing to GitHub.

## What's included

- `test_build.py` - Main script to test building the application with PyInstaller
- `fix_boto_data.py` - Script to fix missing boto3/botocore data files
- `hook-boto3.py` - PyInstaller hook for boto3/botocore
- `app_runtime_hook.py` - Runtime hook for the application
- `update_workflow.py` - Script to update the GitHub workflow file with the fixes

## How to use

1. Make sure PyInstaller is installed:
   ```
   pip install pyinstaller
   ```

2. Run the test build script:
   ```
   python test_build.py
   ```

3. If the test is successful, update the GitHub workflow:
   ```
   python update_workflow.py
   ```

## Common Issues Fixed

1. **Missing boto3/botocore data files**:
   - The application was failing because it couldn't find the boto3/botocore data files
   - Fixed by including all data files in the package and adding a runtime hook to create missing directories

2. **WebSocket connection errors**:
   - The application was constantly trying to reconnect to the WebSocket server and logging errors
   - Fixed by suppressing WebSocket errors and adding retry logic

3. **Missing environment files**:
   - The application couldn't find the .env file and other necessary files
   - Fixed by creating these files at runtime if they don't exist

4. **PyInstaller packaging issues**:
   - Changed the PyInstaller packaging method to include all dependencies
   - Added proper runtime hooks to fix common issues

## After updating the workflow

After running `update_workflow.py`, push the changes to GitHub:

```
git add .github/workflows/test-build.yml
git commit -m "Fix PyInstaller packaging issues"
git push
```

This will trigger a new workflow run on GitHub with the fixed configuration.

## Manual testing

If you want to test the built application manually:

1. Build the application:
   ```
   pyinstaller local_test.spec
   ```

2. Run the built application:
   ```
   dist\TallyfyAI\TallyfyAI.exe
   ```

3. Check for any errors in the console output 