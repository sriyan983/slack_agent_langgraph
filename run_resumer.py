#!/usr/bin/env python3
"""
Run script for the message processor
"""

import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Now import and run the message processor
from resumer.resume_script import interactive_resume

if __name__ == "__main__":
    print("🔄 Starting message processor...")
    interactive_resume() 