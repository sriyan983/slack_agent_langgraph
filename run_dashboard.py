#!/usr/bin/env python3
"""
Launcher script for the Slack Message Dashboard
"""

import subprocess
import sys
import os
from pathlib import Path

def main():
    # Get the directory where this script is located
    script_dir = Path(__file__).parent
    dashboard_path = script_dir / "ui/message_dashboard.py"
    
    # Check if the dashboard file exists
    if not dashboard_path.exists():
        print(f"❌ Dashboard file not found: {dashboard_path}")
        sys.exit(1)
    
    print("🚀 Starting Slack Message Dashboard...")
    print(f"📁 Dashboard path: {dashboard_path}")
    print("🌐 Dashboard will be available at: http://localhost:8501")
    print("🛑 Press Ctrl+C to stop the dashboard")
    print("-" * 50)
    
    try:
        # Run streamlit
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", 
            str(dashboard_path),
            "--server.port", "8501",
            "--server.address", "0.0.0.0"
        ])
    except KeyboardInterrupt:
        print("\n🛑 Dashboard stopped by user")
    except Exception as e:
        print(f"❌ Error running dashboard: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 