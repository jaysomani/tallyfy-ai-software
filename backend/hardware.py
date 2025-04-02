# hardware.py
import os
import platform
import subprocess
import uuid

def get_hardware_id():
    """
    Returns a unique hardware identifier.
    On Windows, it tries to use 'wmic csproduct get uuid'; otherwise, it falls back to the MAC address.
    """
    if platform.system() == "Windows":
        try:
            output = subprocess.check_output("wmic csproduct get uuid", shell=True)
            # The output usually contains two lines; the second line is the UUID.
            hwid = output.decode().split("\n")[1].strip()
            if hwid:
                return hwid
        except Exception:
            pass
    # For Linux/Mac or as a fallback, use the MAC address.
    return str(uuid.getnode())
