#!/usr/bin/env python3
"""
Streamlit Dashboard for Slack Message Management
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import requests
import json
import sys
import os

# Add the parent directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.db import (
    get_messages_needing_human_response, 
    get_message_by_id, 
    update_slack_response_status,
    SessionLocal,
    SlackMessage
)

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8002")

def get_all_messages():
    """Get all messages from database"""
    try:
        db = SessionLocal()
        messages = db.query(SlackMessage).order_by(SlackMessage.created_at.desc()).all()
        return messages
    except Exception as e:
        st.error(f"Error fetching messages: {e}")
        return []
    finally:
        db.close()

def get_messages_by_classification(classification):
    """Get messages filtered by classification"""
    try:
        db = SessionLocal()
        if classification == "all":
            messages = db.query(SlackMessage).order_by(SlackMessage.created_at.desc()).all()
        else:
            messages = db.query(SlackMessage).filter(
                SlackMessage.classification == classification
            ).order_by(SlackMessage.created_at.desc()).all()
        return messages
    except Exception as e:
        st.error(f"Error fetching {classification} messages: {e}")
        return []
    finally:
        db.close()

def submit_human_feedback(message_id, feedback, slack_response):
    """Submit human feedback via resume API"""
    try:
        # Get message details
        message = get_message_by_id(message_id)
        if not message or not message.api_thread_id:
            st.error("Message not found or missing thread ID")
            return False
        
        # Prepare resume request
        resume_request = {
            "thread_id": message.api_thread_id,
            "human_feedback": {
                "feedback": feedback,
                "slack_response": slack_response
            }
        }
        
        # Call resume API
        response = requests.post(f"{API_BASE_URL}/resume", json=resume_request)
        
        if response.status_code == 200:
            result = response.json()
            st.success("Feedback submitted successfully!")
            
            # Send Slack response if provided
            if slack_response:
                slack_request = {
                    "channel": message.channel,
                    "message": slack_response
                }
                if message.ts:
                    slack_request["thread_ts"] = message.ts
                
                slack_response_api = requests.post(f"{API_BASE_URL}/send_slack_response", json=slack_request)
                
                if slack_response_api.status_code == 200:
                    st.success("Slack response sent successfully!")
                    update_slack_response_status(message_id, "yes", slack_response)
                else:
                    st.error("Failed to send Slack response")
                    update_slack_response_status(message_id, "failed")
                    return False
            else:
                update_slack_response_status(message_id, "yes")
            
            return True
        else:
            st.error(f"Failed to submit feedback: {response.status_code}")
            return False
            
    except Exception as e:
        st.error(f"Error submitting feedback: {e}")
        return False

def display_message_card(message, show_feedback_form=False):
    """Display a single message as a card"""
    with st.container():
        st.markdown("---")
        
        # Message header
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col1:
            st.markdown(f"**Message #{message.id}**")
            st.markdown(f"*{message.created_at.strftime('%Y-%m-%d %H:%M')}*")
        
        with col2:
            st.markdown(f"**Channel:** {message.channel}")
            st.markdown(f"**User:** {message.user}")
        
        with col3:
            # Classification badge
            if message.classification == "respond":
                st.markdown("🔴 **Respond**")
            elif message.classification == "notify":
                st.markdown("🟡 **Notify**")
            elif message.classification == "ignore":
                st.markdown("⚪ **Ignore**")
            else:
                st.markdown("❓ **Unknown**")
            
            # Status badge - only show for messages that need responses
            if message.classification == "ignore":
                st.markdown("🚫 **No Response**")
            elif message.slack_responded == "yes":
                st.markdown("✅ **Responded**")
            elif message.slack_responded == "failed":
                st.markdown("❌ **Failed**")
            else:
                st.markdown("⏳ **Pending**")
        
        # Message text
        st.markdown(f"**Message:** {message.text}")
        
        # Reasoning (if available)
        if message.reasoning:
            with st.expander("AI Reasoning"):
                st.markdown(message.reasoning)
        
        # Slack response information (for respond and notify messages)
        if message.classification in ["respond", "notify"]:
            response_info = []
            
            # Show notification message for notify messages
            if message.classification == "notify" and message.notification_message:
                response_info.append(f"**Notification Sent:** {message.notification_message}")
            
            # Show Slack response status and actual response
            if message.slack_responded == "yes":
                response_info.append("✅ **Slack Response:** Sent successfully")
                if message.slack_response_text:
                    response_info.append(f"**Response Text:** {message.slack_response_text}")
            elif message.slack_responded == "failed":
                response_info.append("❌ **Slack Response:** Failed to send")
            else:
                response_info.append("⏳ **Slack Response:** Pending")
            
            # Show thread information if available
            if message.thread_ts:
                response_info.append(f"**Thread:** {message.thread_ts}")
            
            if response_info:
                with st.expander("📤 Slack Response Details"):
                    for info in response_info:
                        st.markdown(info)
        
        # Feedback form for respond messages
        if show_feedback_form and message.classification == "respond" and message.slack_responded != "yes":
            with st.expander("📝 Provide Human Feedback", expanded=True):
                feedback = st.text_area(
                    "Analysis/Feedback:",
                    placeholder="Provide your analysis of this message...",
                    key=f"feedback_{message.id}"
                )
                
                slack_response = st.text_area(
                    "Slack Response:",
                    placeholder="Enter the response to send to Slack...",
                    key=f"slack_response_{message.id}"
                )
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Submit Feedback", key=f"submit_{message.id}"):
                        if feedback and slack_response:
                            success = submit_human_feedback(message.id, feedback, slack_response)
                            if success:
                                st.rerun()  # Refresh the page
                        else:
                            st.error("Please provide both feedback and Slack response")
                
                with col2:
                    if st.button("Cancel", key=f"cancel_{message.id}"):
                        st.rerun()

def main():
    st.set_page_config(
        page_title="Slack Message Dashboard",
        page_icon="📊",
        layout="wide"
    )
    
    st.title("📊 Slack Message Dashboard")
    st.markdown("Manage and respond to Slack messages with AI assistance")
    
    # Sidebar filters
    st.sidebar.header("Filters")
    
    # Classification filter
    classification = st.sidebar.selectbox(
        "Classification:",
        ["all", "respond", "notify", "ignore"],
        format_func=lambda x: x.title()
    )
    
    # Status filter
    status_filter = st.sidebar.selectbox(
        "Status:",
        ["all", "pending", "responded", "failed"],
        format_func=lambda x: x.title()
    )
    
    # Search filter
    search_term = st.sidebar.text_input("Search messages:", placeholder="Enter text to search...")
    
    # Refresh button
    if st.sidebar.button("🔄 Refresh"):
        st.rerun()
    
    # Get messages based on filters
    messages = get_messages_by_classification(classification)
    
    # Apply additional filters
    if status_filter != "all":
        if status_filter == "pending":
            # For pending, exclude ignore messages and only show messages that need responses
            messages = [m for m in messages if m.slack_responded == "no" and m.classification != "ignore"]
        elif status_filter == "responded":
            messages = [m for m in messages if m.slack_responded == "yes"]
        elif status_filter == "failed":
            messages = [m for m in messages if m.slack_responded == "failed"]
    
    if search_term:
        messages = [m for m in messages if search_term.lower() in m.text.lower()]
    
    # Display statistics
    col1, col2, col3, col4, col5 = st.columns(5)
    
    all_messages = get_all_messages()
    respond_count = len([m for m in all_messages if m.classification == "respond"])
    notify_count = len([m for m in all_messages if m.classification == "notify"])
    ignore_count = len([m for m in all_messages if m.classification == "ignore"])
    # Count messages that actually needed responses and got them
    responded_count = len([m for m in all_messages if m.slack_responded == "yes" and m.classification in ["respond", "notify"]])
    
    with col1:
        st.metric("Total Messages", len(all_messages))
    with col2:
        st.metric("Respond", respond_count)
    with col3:
        st.metric("Notify", notify_count)
    with col4:
        st.metric("Ignore", ignore_count)
    with col5:
        st.metric("Responded", responded_count)
    
    # Display messages
    st.subheader(f"Messages ({len(messages)} found)")
    
    if not messages:
        st.info("No messages found matching the current filters.")
        return
    
    # Show feedback form for respond messages
    show_feedback = classification == "respond"
    
    # Display messages
    for message in messages:
        display_message_card(message, show_feedback_form=show_feedback)
    
    # Footer
    st.markdown("---")
    st.markdown("*Dashboard last updated: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "*")

if __name__ == "__main__":
    main() 