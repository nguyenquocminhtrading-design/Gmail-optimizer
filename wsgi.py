# WSGI / ASGI deployment configuration for PythonAnywhere
import sys
import os

# Add application directory to sys.path
path = os.path.dirname(os.path.abspath(__file__))
if path not in sys.path:
    sys.path.insert(0, path)

from main import app as application
