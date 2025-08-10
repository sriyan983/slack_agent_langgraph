#!/usr/bin/env python3
"""
Migration script to add slack_response_text column to existing databases
"""

import sys
import os
from sqlalchemy import text

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import engine, SessionLocal

def migrate_add_slack_response_text():
    """Add slack_response_text column to slack_messages table"""
    try:
        db = SessionLocal()
        
        # Check if column already exists
        result = db.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'slack_messages' 
            AND column_name = 'slack_response_text'
        """))
        
        if result.fetchone():
            print("✅ Column 'slack_response_text' already exists")
            return True
        
        # Add the new column
        db.execute(text("""
            ALTER TABLE slack_messages 
            ADD COLUMN slack_response_text TEXT
        """))
        
        db.commit()
        print("✅ Successfully added 'slack_response_text' column to slack_messages table")
        return True
        
    except Exception as e:
        print(f"❌ Error adding column: {e}")
        db.rollback()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    print("🔄 Running migration to add slack_response_text column...")
    success = migrate_add_slack_response_text()
    if success:
        print("🎉 Migration completed successfully!")
    else:
        print("❌ Migration failed!")
        sys.exit(1) 