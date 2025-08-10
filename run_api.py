#!/usr/bin/env python3
"""
Run script for the API server
"""

import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Now import and run the API
from api.api import app
import uvicorn

if __name__ == "__main__":
    print("🚀 Starting API server...")
    uvicorn.run(app, host="0.0.0.0", port=8002) 