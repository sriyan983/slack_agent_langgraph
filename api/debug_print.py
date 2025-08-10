#!/usr/bin/env python3
"""
Debug print utility for FastAPI
"""

import sys
import os

def debug_print(*args, **kwargs):
    """Print that forces flush for FastAPI environments"""
    print(*args, **kwargs, flush=True)
    sys.stdout.flush()

# Usage example:
# from debug_print import debug_print
# debug_print("This will show up in FastAPI!") 