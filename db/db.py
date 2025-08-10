import os
import json
from datetime import datetime, timedelta
from sqlalchemy import create_engine, Column, String, DateTime, Text, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

# PostgreSQL Configuration
POSTGRES_HOST = "localhost"
POSTGRES_PORT = "5434"
POSTGRES_DB = "slack_messages"
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")

# Database setup
DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# SQLAlchemy Model
class SlackMessage(Base):
    __tablename__ = "slack_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    envelope_id = Column(String, nullable=False)
    channel = Column(String, nullable=False)
    user = Column(String, nullable=False)
    text = Column(Text, nullable=False)
    ts = Column(String, nullable=False)
    thread_ts = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    processed = Column(String, default="pending")  # pending, processed, ignored
    
    # API processing results
    api_thread_id = Column(String, nullable=True)
    api_message_id = Column(String, nullable=True)
    classification = Column(String, nullable=True)  # ignore, notify, respond
    reasoning = Column(Text, nullable=True)
    notification_message = Column(Text, nullable=True)
    events_data = Column(Text, nullable=True)  # JSON string of events
    processed_at = Column(DateTime, nullable=True)
    
    # Slack response tracking
    slack_responded = Column(String, default="no")  # no, yes, failed
    slack_responded_at = Column(DateTime, nullable=True)
    slack_response_text = Column(Text, nullable=True)  # Actual response sent to Slack

# Create tables
def create_tables():
    """Create all tables in the database"""
    Base.metadata.create_all(bind=engine)
    print(f"✅ Database tables created successfully")

def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def save_message_to_db(envelope_id: str, channel: str, user: str, text: str, ts: str, thread_ts: str = None):
    """Save message to PostgreSQL database"""
    try:
        db = SessionLocal()
        
        # Check if message already exists
        existing_message = db.query(SlackMessage).filter(
            SlackMessage.envelope_id == envelope_id,
            SlackMessage.channel == channel,
            SlackMessage.user == user,
            SlackMessage.ts == ts
        ).first()
        
        if existing_message:
            print(f"🔄 Message already exists in DB: {envelope_id}")
            return existing_message.id
        
        # Create new message record
        new_message = SlackMessage(
            envelope_id=envelope_id,
            channel=channel,
            user=user,
            text=text,
            ts=ts,
            thread_ts=thread_ts,
            processed="pending"
        )
        
        db.add(new_message)
        db.commit()
        db.refresh(new_message)
        
        print(f"✅ Message saved to DB with ID: {new_message.id}")
        return new_message.id
        
    except Exception as e:
        print(f"❌ Error saving message to DB: {e}")
        db.rollback()
        return None
    finally:
        db.close()

def get_pending_messages():
    """Get all pending messages from database"""
    try:
        db = SessionLocal()
        messages = db.query(SlackMessage).filter(SlackMessage.processed == "pending").all()
        print(f"🔍 Found {len(messages)} pending messages")
        return messages
    except Exception as e:
        print(f"❌ Error getting pending messages: {e}")
        return []
    finally:
        db.close()

def get_messages_needing_slack_response():
    """Get messages that need Slack responses (notify classification but no response sent)"""
    try:
        db = SessionLocal()
        messages = db.query(SlackMessage).filter(
            SlackMessage.classification == "notify",
            SlackMessage.slack_responded == "no"
        ).all()
        return messages
    except Exception as e:
        print(f"❌ Error getting messages needing Slack response: {e}")
        return []
    finally:
        db.close()

def get_messages_needing_human_response():
    """Get messages that need human response (respond classification)"""
    try:
        db = SessionLocal()
        messages = db.query(SlackMessage).filter(
            SlackMessage.classification == "respond"
        ).all()
        return messages
    except Exception as e:
        print(f"❌ Error getting messages needing human response: {e}")
        return []
    finally:
        db.close()

def update_message_status(message_id: int, status: str):
    """Update message processing status"""
    try:
        db = SessionLocal()
        message = db.query(SlackMessage).filter(SlackMessage.id == message_id).first()
        if message:
            message.processed = status
            db.commit()
            print(f"✅ Message {message_id} status updated to: {status}")
            return True
        else:
            print(f"❌ Message {message_id} not found")
            return False
    except Exception as e:
        print(f"❌ Error updating message status: {e}")
        db.rollback()
        return False
    finally:
        db.close()

def update_processing_results(message_id: int, api_result: dict):
    """Update message with API processing results"""
    try:
        db = SessionLocal()
        message = db.query(SlackMessage).filter(SlackMessage.id == message_id).first()
        
        if message:
            # Extract data from API result
            message.api_thread_id = api_result.get("thread_id")
            message.api_message_id = api_result.get("message_id")
            message.events_data = json.dumps(api_result.get("events", []))
            message.processed_at = datetime.utcnow()
            
            # Extract classification and other data from events
            events = api_result.get("events", [])
            for event in events:
                if isinstance(event, dict):
                    if 'classify_message' in event:
                        classify_data = event['classify_message']
                        if isinstance(classify_data, dict):
                            message.classification = classify_data.get('classification')
                            message.reasoning = classify_data.get('reasoning')
                    elif 'ai_notification' in event:
                        notification_data = event['ai_notification']
                        if isinstance(notification_data, dict):
                            message.notification_message = notification_data.get('notification_message')
            
            # Update status based on classification
            if message.classification:
                message.processed = f"processed_{message.classification}"
            else:
                message.processed = "processed"
            
            db.commit()
            print(f"✅ Processing results updated for message {message_id}")
            return True
        else:
            print(f"❌ Message {message_id} not found")
            return False
            
    except Exception as e:
        print(f"❌ Error updating processing results: {e}")
        db.rollback()
        return False
    finally:
        db.close()

def update_slack_response_status(message_id: int, status: str, response_text: str = None):
    """Update Slack response status and text for a message"""
    try:
        db = SessionLocal()
        message = db.query(SlackMessage).filter(SlackMessage.id == message_id).first()
        
        if message:
            message.slack_responded = status
            if status == "yes":
                message.slack_responded_at = datetime.utcnow()
            if response_text:
                message.slack_response_text = response_text
            db.commit()
            print(f"✅ Slack response status updated for message {message_id}: {status}")
            return True
        else:
            print(f"❌ Message {message_id} not found")
            return False
            
    except Exception as e:
        print(f"❌ Error updating Slack response status: {e}")
        db.rollback()
        return False
    finally:
        db.close()

def update_human_feedback(message_id: int, human_feedback: str, human_slack_response: str):
    """Update message with human feedback and response"""
    try:
        db = SessionLocal()
        message = db.query(SlackMessage).filter(SlackMessage.id == message_id).first()
        
        if message:
            # Store human's feedback and response
            message.notification_message = human_slack_response  # Override AI response with human's
            message.reasoning = human_feedback  # Store human's analysis
            message.processed = "completed"  # Mark as completed
            message.slack_responded = "yes"  # Mark as responded
            message.slack_responded_at = datetime.utcnow()
            
            db.commit()
            print(f"✅ Human feedback updated for message {message_id}")
            print(f"   Feedback: {human_feedback[:50]}...")
            print(f"   Slack Response: {human_slack_response}")
            return True
        else:
            print(f"❌ Message {message_id} not found")
            return False
            
    except Exception as e:
        print(f"❌ Error updating human feedback: {e}")
        db.rollback()
        return False
    finally:
        db.close()

def get_message_by_id(message_id: int):
    """Get message by ID"""
    try:
        db = SessionLocal()
        message = db.query(SlackMessage).filter(SlackMessage.id == message_id).first()
        return message
    except Exception as e:
        print(f"❌ Error getting message by ID: {e}")
        return None
    finally:
        db.close()

def delete_old_messages(days_old: int = 30):
    """Delete messages older than specified days"""
    try:
        db = SessionLocal()
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        deleted_count = db.query(SlackMessage).filter(SlackMessage.created_at < cutoff_date).delete()
        db.commit()
        print(f"✅ Deleted {deleted_count} messages older than {days_old} days")
        return deleted_count
    except Exception as e:
        print(f"❌ Error deleting old messages: {e}")
        db.rollback()
        return 0
    finally:
        db.close()

# Initialize database when module is imported
if __name__ == "__main__":
    create_tables()
    print(f"🗄️  Database URL: {DATABASE_URL}")
else:
    # Create tables when module is imported
    create_tables() 