import os
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.web import WebClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse
from dotenv import load_dotenv
import time
from datetime import datetime
from db.db import save_message_to_db, DATABASE_URL

load_dotenv()

# Slack Configuration
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")

# --------------------------
#  Initialize Clients
# --------------------------
web_client = WebClient(token=SLACK_BOT_TOKEN)
socket_client = SocketModeClient(app_token=SLACK_APP_TOKEN, web_client=web_client)

# Get bot's own user ID to avoid responding to itself
try:
    auth_response = web_client.auth_test()
    BOT_USER_ID = auth_response["user_id"]
    print(f"🤖 Bot user ID: {BOT_USER_ID}")
except Exception as e:
    print(f"❌ Error getting bot user ID: {e}")
    BOT_USER_ID = None

# Track API start time to ignore old messages
API_START_TIME = time.time()
print(f"🚀 Pipeline started at: {datetime.fromtimestamp(API_START_TIME)}")

# Track processed messages to prevent duplicates
PROCESSED_MESSAGES = set()

def capture_message_for_processing(envelope_id: str, channel: str, user: str, text: str, ts: str, thread_ts: str = None):
    """Capture message and save to database"""
    
    # Create unique message identifier
    message_key = f"{channel}:{ts}:{user}:{text}"
    
    print(f"🔄 Message key: {message_key}")
    
    # Check if message was already processed
    if message_key in PROCESSED_MESSAGES:
        print(f"🔄 Skipping duplicate message: {message_key}")
        return
    
    # Add to processed set
    PROCESSED_MESSAGES.add(message_key)
    
    # Save to database using the imported function
    message_id = save_message_to_db(envelope_id, channel, user, text, ts, thread_ts)
    
    if message_id:
        print(f"📩 Message captured and saved to database!")
        print(f"   Message ID: {message_id}")
        print(f"   Channel: {channel}")
        print(f"   User: {user}")
        print(f"   Text: {text[:50]}...")
    else:
        print(f"❌ Failed to save message to database")

# --------------------------
#  Message Event Handler
# --------------------------
def process(client: SocketModeClient, req: SocketModeRequest):
    try:
        if req.type == "events_api":
            event = req.payload["event"]
            print(f"🔄 Received event: {event}")
            # Handle normal messages (no subtype means not a bot/system message)
            if event.get("type") == "message" and "subtype" not in event:
                channel = event["channel"]
                user = event.get("user", "")
                text = event.get("text", "")
                ts = event.get("ts", "")
                thread_ts = event.get("thread_ts", None)
                envelope_id = req.envelope_id

                print(f"🔄 Received event: {event}")
                print(f"📊 Message details: user={user}, text='{text}', ts={ts}")
                
                # Skip messages from the bot itself to prevent infinite loops
                if BOT_USER_ID and user == BOT_USER_ID:
                    print(f"🔄 Skipping bot's own message")
                    return
                
                # Skip messages that start with bot identifier to prevent infinite loops
                if text.startswith("[BOT_RESPONSE]"):
                    print(f"🔄 Skipping bot response message: {text[:50]}...")
                    return
                
                # Skip messages that start with @Narayan (bot messages)
                if text.startswith("@Narayan"):
                    print(f"🔄 Skipping @Narayan message: {text[:50]}...")
                    return
                    
                # Skip messages older than API start time (with buffer for socket mode unpredictability)
                message_time = float(ts)
                current_time = time.time()
                
                # Add 5 second buffer to handle socket mode delays
                if message_time < (API_START_TIME - 5):
                    print(f"⏰ Skipping old message (ts={ts}, message_time={message_time}, API started at {API_START_TIME})")
                    return
                
                # Also skip messages that are too old (more than 1 hour old)
                if message_time < (current_time - 3600):
                    print(f"⏰ Skipping very old message (ts={ts}, message_time={message_time}, current_time={current_time})")
                    return
                    
                if channel == "C09A2NZNEBS":
                    print(f"📩 Received from {user} in {channel}: {text}")
                    print(f"📋 Message details: ts={ts}, thread_ts={thread_ts}")

                    # Capture message for processing (no immediate response)
                    print(f"🔄 WILL SAVE TO DB NOW")
                    capture_message_for_processing(envelope_id, channel, user, text, ts, thread_ts)

            # Acknowledge the event so Slack doesn't retry
            response = SocketModeResponse(envelope_id=req.envelope_id)
            client.send_socket_mode_response(response)
    except Exception as e:  
        print(f"❌ Error processing event: {e}")

# --------------------------
#  Register Handler & Start
# --------------------------
socket_client.socket_mode_request_listeners.append(process)

if __name__ == "__main__":
    print("🤖 Slack Pipeline is running via Socket Mode...")
    print(f"🗄️  Database: {DATABASE_URL}")
    print("📝 Pipeline will capture messages and save to PostgreSQL")
    socket_client.connect()
    # Keep the script running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n�� Pipeline stopped") 