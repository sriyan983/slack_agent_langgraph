# api.py
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
import uuid
from langgraph.types import Command
from agent_graph.graph import graph  # Import from the existing graph.py file
from datetime import datetime
from typing import Dict, Any, Optional
# Removed requests import - no longer needed
import os
from dotenv import load_dotenv
import json
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# ---------- FastAPI App ----------
app = FastAPI()

# Store thread states in memory for now
# Key = thread_id (UUID), Value = user session config
thread_store = {}

# Removed message_store - now handled by database in message_processor.py

# Slack client for sending responses
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
slack_client = None
if SLACK_BOT_TOKEN:
    from slack_sdk.web import WebClient
    slack_client = WebClient(token=SLACK_BOT_TOKEN)

class StartRequest(BaseModel):
    input: str
    slack_ts: Optional[str] = None
    slack_channel: Optional[str] = None
    slack_user: Optional[str] = None
    slack_thread_ts: Optional[str] = None
    slack_text: Optional[str] = None

class HumanFeedback(BaseModel):
    feedback: str = "Your analysis or feedback about the message"
    slack_response: Optional[str] = None
    
    class Config:
        schema_extra = {
            "example": {
                "feedback": "This is a technical issue that requires immediate attention. The user is experiencing a critical system failure.",
                "slack_response": "I understand you're having a critical issue. Let me escalate this to our technical team immediately. They'll contact you within 15 minutes."
            }
        }

class ResumeRequest(BaseModel):
    thread_id: str
    human_feedback: HumanFeedback
    
    class Config:
        schema_extra = {
            "example": {
                "thread_id": "123e4567-e89b-12d3-a456-426614174000",
                "human_feedback": {
                    "feedback": "This is a technical issue that requires immediate attention. The user is experiencing a critical system failure.",
                    "slack_response": "I understand you're having a critical issue. Let me escalate this to our technical team immediately. They'll contact you within 15 minutes."
                }
            }
        }

class ResponseRequest(BaseModel):
    message: str

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# Removed message endpoints - now handled by database queries in message_processor.py

def send_slack_response(channel: str, message: str, thread_ts: str = None):
    """Send response to Slack channel"""
    if not slack_client:
        logger.error("❌ Slack client not initialized")
        return False
    
    try:
        # Add bot identifier to prevent infinite loops
        bot_message = f"[BOT_RESPONSE] {message}"
        
        response = slack_client.chat_postMessage(
            channel=channel,
            text=bot_message,
            thread_ts=thread_ts
        )
        return response["ok"]
    except Exception as e:
        logger.error(f"❌ Error sending Slack response: {e}")
        return False

def serialize_event(event):
    """Convert event to JSON-serializable format"""
    try:
        # If it's already a dict, return it
        if isinstance(event, dict):
            return event
        # If it's a string, try to parse it as JSON
        elif isinstance(event, str):
            import json
            return json.loads(event)
        # For other types, convert to dict if possible
        else:
            return event.__dict__ if hasattr(event, '__dict__') else str(event)
    except Exception as e:
        logger.error(f"Error serializing event: {e}")
        return {"error": f"Could not serialize event: {str(event)}"}

# Removed store_message_result function - now handled by message_processor.py

@app.post("/start")
def start_execution(req: StartRequest):
    """Start the graph execution until first interrupt."""
    logger.info(f"API START REQUEST --->: {req}")
    try:
        thread_id = str(uuid.uuid4())
        thread = {"configurable": {"thread_id": thread_id}}

        output_events = []
        for event in graph.stream({"input": req.input}, thread, stream_mode="updates"):
            serialized_event = serialize_event(event)
            output_events.append(serialized_event)

        # Store thread in memory for resume functionality
        thread_store[thread_id] = thread
        
        # Generate a simple message ID for reference
        message_id = f"msg_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
    except Exception as e:
        logger.error(f"Error in graph execution: {e}")
        thread_id = None
        message_id = None
        output_events = []

    return {
        "status": "completed",
        "thread_id": thread_id,
        "message_id": message_id,
        "events": output_events
    }

@app.post("/resume")
def resume_execution(req: ResumeRequest):
    """
    Resume graph execution after receiving user feedback.
    
    This endpoint allows resuming a conversation thread that was paused for human review.
    The human feedback is used to continue the workflow, and optionally a Slack response
    can be provided to send to the original channel.
    
    Example request:
    ```json
    {
      "thread_id": "123e4567-e89b-12d3-a456-426614174000",
      "human_feedback": {
        "feedback": "This is a technical issue requiring immediate attention",
        "slack_response": "I'll escalate this to our technical team right away"
      }
    }
    ```
    """
    thread_id = req.thread_id
    if thread_id not in thread_store:
        return {"error": "Invalid thread_id"}

    thread = thread_store[thread_id]
    human_feedback = req.human_feedback

    logger.info(f"RESUME REQUEST --->: {req}")
    
    # Extract human's Slack response if provided
    slack_response = human_feedback.slack_response
    
    # Prepare resume command
    resume_dict = {
        "feedback": human_feedback.feedback,
        "optional_data": thread_id
    }
    logger.info(f"Resuming with: {resume_dict}")
    resume_cmd = Command(resume=resume_dict)

    output_events = []
    for event in graph.stream(resume_cmd, thread, stream_mode="updates"):
        serialized_event = serialize_event(event)
        output_events.append(serialized_event)

    # If human provided a Slack response, send it
    if slack_response:
        logger.info(f"📤 Sending human's Slack response: {slack_response}")
        # Note: In a real implementation, you'd need to get the channel from the database
        # For now, we'll just log it
        logger.info(f"   Human response: {slack_response}")
        logger.info(f"   (Channel would be retrieved from database using thread_id)")

    return {
        "status": "resumed",
        "thread_id": thread_id,
        "events": output_events,
        "human_slack_response": slack_response
    }

# Removed /respond/ai/{message_id} and /respond/human/{message_id} endpoints
# Slack responses are now handled by message_processor.py and database

class SlackResponseRequest(BaseModel):
    channel: str
    message: str
    thread_ts: Optional[str] = None
    
    class Config:
        schema_extra = {
            "example": {
                "channel": "C1234567890",
                "message": "Your response message here",
                "thread_ts": "1234567890.123456"
            }
        }

@app.post("/send_slack_response")
def send_slack_response_endpoint(req: SlackResponseRequest):
    """
    Send response to Slack channel.
    
    This endpoint sends a message to a specific Slack channel, optionally in a thread.
    
    Example request:
    ```json
    {
      "channel": "C1234567890",
      "message": "Your response message here",
      "thread_ts": "1234567890.123456"
    }
    ```
    """
    try:
        success = send_slack_response(req.channel, req.message, req.thread_ts)
        
        if success:
            return {"status": "success", "message": "Slack response sent"}
        else:
            return {"status": "error", "message": "Failed to send Slack response"}
            
    except Exception as e:
        return {"status": "error", "message": f"Error: {str(e)}"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)

    """
   9851cebf-4c03-441a-844e-d6fa27d01cd4
   d01409f7-2d95-4fd2-9ae3-70d69d8de787
   78e53357-9fa4-45d7-848e-f2c819c75165

   I'll be working from home today due to a doctor's appointment : notify
   thanks! : ignore
   can you review this grammar issue: respond
    """
