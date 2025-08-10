#!/usr/bin/env python3
"""
Resume script to test human-in-the-loop workflow
"""

import sys
import os
import requests
import json

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.db import get_messages_needing_human_response, get_message_by_id, update_slack_response_status
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8002")

def get_messages_for_human_review():
    """Get messages that need human response"""
    try:
        messages = get_messages_needing_human_response()
        return messages
    except Exception as e:
        print(f"❌ Error getting messages for human review: {e}")
        return []

def resume_message_processing(message_id: int, human_feedback: str, slack_response: str):
    """Resume processing for a specific message with human feedback"""
    try:
        # Get message from database
        message = get_message_by_id(message_id)
        if not message:
            print(f"❌ Message {message_id} not found")
            return False
        
        # Check if message has thread_id
        if not message.api_thread_id:
            print(f"❌ Message {message_id} has no thread_id")
            return False
        
        print(f"🔄 Resuming message {message_id}")
        print(f"   Thread ID: {message.api_thread_id}")
        print(f"   Human Feedback: {human_feedback}")
        print(f"   Slack Response: {slack_response}")
        
        # Prepare resume request
        resume_request = {
            "thread_id": message.api_thread_id,
            "human_feedback": {
                "feedback": human_feedback,
                "slack_response": slack_response
            }
        }
        
        # Call resume API
        print(f"📡 Calling resume API...")
        response = requests.post(f"{API_BASE_URL}/resume", json=resume_request)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Resume successful!")
            print(f"   Status: {result.get('status')}")
            print(f"   Events: {len(result.get('events', []))}")
            
            # Send the human's Slack response to Slack
            if slack_response:
                print(f"📤 Sending human's Slack response to Slack...")
                slack_request = {
                    "channel": message.channel,
                    "message": slack_response
                }
                
                # Add thread_ts if it exists
                if message.thread_ts:
                    slack_request["thread_ts"] = message.thread_ts
                
                slack_response_api = requests.post(f"{API_BASE_URL}/send_slack_response", json=slack_request)
                
                if slack_response_api.status_code == 200:
                    print(f"✅ Slack response sent successfully!")
                    # Update Slack response status
                    update_slack_response_status(message_id, "yes")
                else:
                    print(f"❌ Failed to send Slack response: {slack_response_api.status_code}")
                    print(f"   Response: {slack_response_api.text}")
                    # Update Slack response status as failed
                    update_slack_response_status(message_id, "failed")
                    return False
            else:
                print(f"⚠️ No Slack response provided, skipping Slack send")
                # Update Slack response status
                update_slack_response_status(message_id, "yes")
            
            return True
        else:
            print(f"❌ Resume failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error resuming message: {e}")
        return False

def interactive_resume():
    """Interactive resume workflow"""
    print("🤖 Human-in-the-Loop Resume Workflow")
    print("=" * 50)
    
    # Get messages needing human response
    messages = get_messages_for_human_review()
    
    if not messages:
        print("✅ No messages need human response")
        return
    
    print(f"📋 Found {len(messages)} messages needing human response:")
    
    for i, message in enumerate(messages, 1):
        print(f"\n{i}. Message ID: {message.id}")
        print(f"   Channel: {message.channel}")
        print(f"   User: {message.user}")
        print(f"   Text: {message.text}")
        print(f"   Classification: {message.classification}")
        print(f"   Reasoning: {message.reasoning[:100] if message.reasoning else 'N/A'}...")
        print(f"   Thread ID: {message.api_thread_id}")
    
    # Let user select a message
    try:
        choice = int(input(f"\nSelect message to resume (1-{len(messages)}): ")) - 1
        if choice < 0 or choice >= len(messages):
            print("❌ Invalid choice")
            return
        
        selected_message = messages[choice]
        
        # Get human feedback
        print(f"\n📝 Providing feedback for: {selected_message.text}")
        human_feedback = input("Enter your analysis/feedback: ")
        slack_response = input("Enter your Slack response: ")
        
        # Resume processing
        success = resume_message_processing(
            selected_message.id, 
            human_feedback, 
            slack_response
        )
        
        if success:
            print(f"🎉 Successfully resumed message {selected_message.id}")
        else:
            print(f"❌ Failed to resume message {selected_message.id}")
            
    except ValueError:
        print("❌ Please enter a valid number")
    except KeyboardInterrupt:
        print("\n🛑 Cancelled by user")

def test_resume_with_sample_data():
    """Test resume with sample data"""
    print("🧪 Testing Resume with Sample Data")
    print("=" * 50)
    
    # This would be a real message ID from your database
    message_id = int(input("Enter message ID to resume: "))
    
    # Sample human feedback
    human_feedback = "This is a technical issue that requires immediate attention. The user is experiencing a critical system failure."
    slack_response = "I understand you're having a critical issue. Let me escalate this to our technical team immediately. They'll contact you within 15 minutes."
    
    print(f"📝 Sample feedback:")
    print(f"   Analysis: {human_feedback}")
    print(f"   Response: {slack_response}")
    
    success = resume_message_processing(message_id, human_feedback, slack_response)
    
    if success:
        print(f"🎉 Test resume successful!")
    else:
        print(f"❌ Test resume failed!")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Resume human-in-the-loop workflow")
    parser.add_argument("--interactive", action="store_true", help="Run interactive mode")
    parser.add_argument("--test", action="store_true", help="Run test mode")
    
    args = parser.parse_args()
    
    if args.interactive:
        interactive_resume()
    elif args.test:
        test_resume_with_sample_data()
    else:
        print("Usage:")
        print("  python resume_script.py --interactive  # Interactive mode")
        print("  python resume_script.py --test         # Test mode") 