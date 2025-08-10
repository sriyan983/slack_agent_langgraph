#!/usr/bin/env python3
"""
Message Processor - Reads pending messages from database and processes them using api.py logic
"""

import os
import time
import requests
import json
from datetime import datetime
from typing import Dict, Any, Optional
from db.db import (
    get_pending_messages, 
    update_message_status, 
    update_processing_results,
    update_slack_response_status,
    get_message_by_id,
    DATABASE_URL
)
from dotenv import load_dotenv

load_dotenv()

# API Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8002")

class MessageProcessor:
    def __init__(self):
        self.api_base_url = API_BASE_URL
        print(f"🤖 Message Processor initialized")
        print(f"🔗 API Base URL: {self.api_base_url}")
        print(f"🗄️  Database: {DATABASE_URL}")
    
    def format_input_for_api(self, message) -> str:
        """Format message data for API input (channel|user|text)"""
        return f"{message.channel}|{message.user}|{message.text}"
    
    def prepare_api_request(self, message) -> Dict[str, Any]:
        """Prepare request data for API"""
        return {
            "input": self.format_input_for_api(message),
            "slack_ts": message.ts,
            "slack_channel": message.channel,
            "slack_user": message.user,
            "slack_thread_ts": message.thread_ts,
            "slack_text": message.text
        }
    
    def call_api_for_processing(self, message) -> Optional[Dict[str, Any]]:
        """Call the API to process the message"""
        try:
            request_data = self.prepare_api_request(message)
            
            print(f"📡 Calling API for message {message.id}")
            print(f"   Input: {request_data['input']}")
            
            response = requests.post(f"{self.api_base_url}/start", json=request_data)
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ API processing successful")
                print(f"   Thread ID: {result.get('thread_id')}")
                print(f"   Message ID: {result.get('message_id')}")
                return result
            else:
                print(f"❌ API call failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Error calling API: {e}")
            return None
    
    def extract_classification_from_events(self, events: list) -> Optional[str]:
        """Extract classification from API events"""
        print("---events full---", events)
        classification_type = None
        
        for event in events:
            print("---event---", event)
            try:
                if isinstance(event, dict):
                    if 'decision_maker' in event:
                        if "classification" in event['decision_maker']:
                            classification_type = event['decision_maker'].get('classification')
                            break
                    elif 'classify_message' in event:
                        classify_data = event['classify_message']
                        if isinstance(classify_data, dict) and "classification" in classify_data:
                            classification_type = classify_data.get('classification')
                            break
                else:
                    print("---event is not a dict---", event)
                        
            except (KeyError, AttributeError) as e:
                print(f"⚠️  Could not parse event: {event}... Error: {e}")
                continue
        
        print(f"---classification_type---: {classification_type}")
        return classification_type
    
    def extract_notification_message_from_events(self, events: list) -> Optional[str]:
        """Extract AI notification message from API events"""
        print("---extracting notification from events---")
        response_text = None
        
        for event in events:
            print("---checking event for notification---", event)
            try:
                if isinstance(event, dict):
                    if 'ai_notification' in event:
                        notification_data = event['ai_notification']
                        if isinstance(notification_data, dict) and "notification_message" in notification_data:
                            response_text = notification_data.get('notification_message')
                            print(f"---found notification message---: {response_text}")
                            break
                else:
                    print("---event is not a dict for notification---", event)
                        
            except (KeyError, AttributeError) as e:
                print(f"⚠️  Could not parse notification event: {event}... Error: {e}")
                continue
        
        print(f"---response_text---: {response_text}")
        return response_text
    
    def send_notification_to_slack(self, message_id: int, notification_message: str) -> bool:
        """Send notification message to Slack using the API's send_slack_response function"""
        try:
            # Get message details from database
            message = get_message_by_id(message_id)
            if not message:
                print(f"❌ Message {message_id} not found in database")
                return False
            
            # Prepare request to send Slack response
            slack_request = {
                "channel": message.channel,
                "message": notification_message
            }
            
            # Only add thread_ts if it exists (not None or empty)
            if message.ts:
                slack_request["thread_ts"] = message.ts
            
            print(f"📡 Sending Slack notification:")
            print(f"   Channel: {message.channel}")
            print(f"   Message: {notification_message}")
            print(f"   Thread TS: {message.thread_ts}")
            
            # Call the API endpoint to send Slack response
            response = requests.post(f"{self.api_base_url}/send_slack_response", json=slack_request)
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Slack notification sent successfully")
                # Update database to mark as responded and store the response text
                update_slack_response_status(message_id, "yes", notification_message)
                return True
            else:
                print(f"❌ Failed to send Slack notification: {response.status_code}")
                print(f"   Response: {response.text}")
                # Update database to mark as failed
                update_slack_response_status(message_id, "failed")
                return False
                
        except Exception as e:
            print(f"❌ Error sending Slack notification: {e}")
            return False
    
    def store_processing_results(self, message_id: int, api_result: Dict[str, Any]) -> bool:
        """Store API processing results in database"""
        try:
            # Extract classification and notification message
            events = api_result.get("events", [])
            classification = self.extract_classification_from_events(events)
            response_text = self.extract_notification_message_from_events(events)
            
            # Use the new database function to store all results
            success = update_processing_results(message_id, api_result)
            
            if success:
                thread_id = api_result.get("thread_id")
                api_message_id = api_result.get("message_id")
                
                print(f"✅ Processing results stored for message {message_id}")
                print(f"   Classification: {classification}")
                print(f"   Response Text: {response_text}")
                print(f"   Thread ID: {thread_id}")
                print(f"   API Message ID: {api_message_id}")
                
                # If classification is 'notify' and we have a response text, send to Slack
                if classification == "notify" and response_text:
                    print(f"🔔 Sending notification to Slack for message {message_id}")
                    slack_success = self.send_notification_to_slack(message_id, response_text)
                    if slack_success:
                        print(f"✅ Notification sent to Slack successfully")
                    else:
                        print(f"❌ Failed to send notification to Slack")
            
            return success
            
        except Exception as e:
            print(f"❌ Error storing processing results: {e}")
            return False
    
    def process_single_message(self, message) -> bool:
        """Process a single pending message"""
        print(f"\n🔄 Processing message {message.id}")
        print(f"   Channel: {message.channel}")
        print(f"   User: {message.user}")
        print(f"   Text: {message.text[:50]}...")
        
        # Call API for processing
        api_result = self.call_api_for_processing(message)
        
        if api_result:
            # Store results in database
            success = self.store_processing_results(message.id, api_result)
            
            if success:
                print(f"✅ Message {message.id} processed successfully")
                return True
            else:
                print(f"❌ Failed to store results for message {message.id}")
                return False
        else:
            print(f"❌ Failed to process message {message.id}")
            # Mark as failed
            update_message_status(message.id, "failed")
            return False
    
    def process_pending_messages(self, batch_size: int = 5) -> int:
        """Process all pending messages in batches"""
        print(f"\n🚀 Starting to process pending messages...")
        
        processed_count = 0
        
        while True:
            # Get pending messages
            pending_messages = get_pending_messages()
            
            if not pending_messages:
                print(f"✅ No more pending messages to process")
                break
            
            # Process batch
            batch = pending_messages[:batch_size]
            print(f"📦 Processing batch of {len(batch)} messages...")
            
            for message in batch:
                success = self.process_single_message(message)
                if success:
                    processed_count += 1
                
                # Small delay between messages to avoid overwhelming the API
                time.sleep(1)
            
            print(f"📊 Batch completed. Total processed: {processed_count}")
            
            # If we processed fewer than batch_size, we're done
            if len(batch) < batch_size:
                break
        
        return processed_count
    
    def run_continuous_processing(self, interval_seconds: int = 30):
        """Run continuous processing with specified interval"""
        print(f"🔄 Starting continuous processing (interval: {interval_seconds}s)")
        
        try:
            while True:
                print(f"\n⏰ Checking for pending messages at {datetime.now()}")
                
                processed_count = self.process_pending_messages()
                
                if processed_count > 0:
                    print(f"✅ Processed {processed_count} messages")
                else:
                    print(f"😴 No messages to process, sleeping...")
                
                time.sleep(interval_seconds)
                
        except KeyboardInterrupt:
            print(f"\n🛑 Continuous processing stopped")

def main():
    """Main function"""
    processor = MessageProcessor()
    
    # Check if API is available
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        if response.status_code == 200:
            print(f"✅ API is available")
        else:
            print(f"❌ API health check failed: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ Cannot connect to API: {e}")
        return
    
    # Process pending messages
    processed_count = processor.process_pending_messages()
    print(f"\n🎉 Processing completed! Total messages processed: {processed_count}")

if __name__ == "__main__":
    main() 