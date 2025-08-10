#!/usr/bin/env python3
"""
Run script for the Slack pipeline
"""

import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Now import and run the Slack pipeline
from slack_pipeline.slack_pipeline import socket_client

if __name__ == "__main__":
    print("🤖 Starting Slack pipeline...")
    socket_client.connect()
    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Slack pipeline stopped") 