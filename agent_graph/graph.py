from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

from langgraph.types import Command, interrupt
from langgraph.checkpoint.memory import InMemorySaver
from langchain.chat_models import init_chat_model

from IPython.display import Image, display

from pydantic import BaseModel, Field
from typing import Literal

from dotenv import load_dotenv
load_dotenv()

import os
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

import random

# Slack assistant triage prompt 
slack_triage_system_prompt = """

< Role >
Your role is to triage incoming Slack messages based upon instructions and background information below.
</ Role >

< Background >
{background}. 
</ Background >

< Instructions >
Categorize each Slack message into one of three categories:
1. IGNORE - Messages that are not worth responding to or tracking
2. NOTIFY - Important information that's worth notification but doesn't require a response
3. RESPOND - Messages that need a direct response
Classify the below Slack message into one of these categories.
</ Instructions >

< Rules >
{slack_triage_instructions}
</ Rules >
"""

# Slack assistant triage user prompt 
slack_triage_user_prompt = """
Please determine how to handle the below Slack message:

Channel: {channel}
From: {author}
Message: {message}"""

# Default background information for IT Head
default_slack_background = """ 
I'm the Head of IT at our organization, responsible for managing technology infrastructure, cybersecurity, system administration, and IT support. I oversee a team of IT professionals and ensure our technology systems run smoothly and securely.
"""

# Default Slack triage instructions for IT Head
default_slack_triage_instructions = """
Slack messages that are not worth responding to:
- Automated bot messages and notifications (unless they're IT system alerts)
- General social chatter and non-work related conversations
- Messages that are clearly meant for other departments
- Spam or suspicious messages
- Messages in channels you're not actively involved with

There are also other things that should be known about, but don't require a Slack response. For these, you should notify (using the `notify` response). Examples of this include:
- Team member status updates (out sick, on vacation, working from home)
- General company announcements
- Project status updates without IT action items
- Non-critical system notifications
- Channel-wide FYI messages that don't require IT intervention
- Meeting reminders and updates

Slack messages that are worth responding to:
- Direct questions or mentions (@username) requiring IT expertise
- IT system issues, outages, or security concerns
- Technical questions about infrastructure, software, or hardware
- Meeting requests or scheduling discussions
- Requests from management or team leads requiring IT input
- Critical bug reports or issues related to IT systems
- Personal reminders or important notifications
- Messages in IT-related channels that require your input
- Direct messages (DMs) from colleagues with IT questions
- Messages that specifically ask for your help or input
- Security incidents or potential threats
- System maintenance or deployment notifications
""" 

# Create a prompt for generating notification messages
notification_system_prompt = """
You are an IT Head assistant. Generate a brief, professional notification message for important information that doesn't require a direct response.

The message should:
- Acknowledge the information received
- Be concise and professional
- Not require any action or response
- Be appropriate for the context and sender
"""

notification_user_prompt = """
Generate a notification message for this information:

Channel: {channel}
From: {author}
Message: {message}
Classification: {classification}
Reasoning: {reasoning}

Create a brief, professional notification that acknowledges this information.
"""

class RouterSchema(BaseModel):
    """Analyze the message and classify it."""

    reasoning: str = Field(
        description="Step-by-step reasoning behind the classification."
    )
    classification: Literal["ignore", "respond", "notify"] = Field(
        description="The classification of an message: 'ignore' for irrelevant messages, "
        "'notify' for important information that doesn't need a response, "
        "'respond' for messages that need a reply",
    )

class NotificationResponseSchema(BaseModel):
    """Schema for the LLM's response to generate a notification message."""
    notification_message: str = Field(
        description="The generated notification message."
    )
    
llm = init_chat_model("openai:gpt-4.1", temperature=0.0)
llm_router = llm.with_structured_output(RouterSchema) 
llm_notification = llm.with_structured_output(NotificationResponseSchema)

class State(TypedDict):
    input: str
    user_feedback: str
    classification: str
    reasoning: str
    author: str
    channel: str
    message: str
    messages: list[dict]
    notification_message: str

#{"input": "C09A2NZNEBS|U0999D7H9M0|Can you sign the RR?"}
def parse_message(message_data: str) -> tuple[str, str, str]:
    parts = message_data.split("|")
    return parts[0].strip(), parts[1].strip(), parts[2].strip()

def process_message(state):
    print("---process_message---", state)
    pass

def classify_message(state: State):
    """Message classifier that uses RouterSchema to classify the message."""
    print("---classify_message---", state)

    message_data = state.get("input", state)
    channel, author, message = parse_message(message_data)
    
    # Use the existing router schema and prompts
    system_prompt = slack_triage_system_prompt.format(
        background=default_slack_background,
        slack_triage_instructions=default_slack_triage_instructions
    )

    user_prompt = slack_triage_user_prompt.format(
        channel=channel, author=author, message=message
    )

    # Get classification using the existing router
    result = llm_router.invoke(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    )

    print("---result---", result)
    
    # Return the classification results to update the state
    return {
        "classification": result.classification,
        "reasoning": result.reasoning,
        "author": author,
        "channel": channel,
        "author": author,
        "message": message,
        "messages": [
            {
                "role": "assistant",
                "content": f"Classification: {result.classification}\nReasoning: {result.reasoning}"
            }
        ]
    }  

    # Fake classification and reasoning
    # classifications = ["respond", "respond", "respond"]
    # reasonings = ["Not important", "Be informed", "Important and respond"]
    # classification = random.choice(classifications)
    # reasoning = random.choice(reasonings)
    # return {
    #     "classification": classification,
    #     "reasoning": reasoning,
    #     "author": author,
    #     "channel": channel,
    #     "author": author,
    #     "message": message,
    #     "messages": [
    #         {
    #             "role": "assistant",
    #             "content": f"Classification: {classification}\nReasoning: {reasoning}"
    #         }
    #     ]
    # }  


def decision_maker(state: State):
    print("---decision_maker---", state)
    # This node just passes through the classification for routing
    return {"classification": state["classification"]}

def human_feedback(state):
    print("---human_feedback---")
    feedback = interrupt("Please provide feedback:")
    print(f"Feedback: {feedback}")
    return {"user_feedback": feedback}

def ai_notification(state: State):
    """Generate a notification message using LLM for important information."""
    print("--- ai_notification ---")
    
    # Use the existing llm instance with structured output for notifications
    llm_with_notification = llm.with_structured_output(NotificationResponseSchema)
    result = llm_notification.invoke(
        [
            {"role": "system", "content": notification_system_prompt},
            {"role": "user", "content": notification_user_prompt.format(
                channel=state["channel"],
                author=state["author"],
                message=state["message"],
                classification=state["classification"],
                reasoning=state["reasoning"]
            )},
        ]
    )
    
    print(f"🔔 AI Notification: {result.notification_message}")
    
    return {
        "notification_message": result.notification_message,
        "messages": state.get("messages", []) + [
            {
                "role": "assistant", 
                "content": f"🔔 Notification: {result.notification_message}"
            }
        ]
    }

    # Fake notification message
    # notification_message = "Thanks for the message!"
    # return {
    #     "notification_message": notification_message,
    #     "messages": state.get("messages", []) + [
    #         {
    #             "role": "assistant", 
    #             "content": f"🔔 Notification: {notification_message}"
    #         }
    #     ]
    # }

def end(state: State):
    print("--- end ---")
    return {}

builder = StateGraph(State)
builder.add_node("process_message", process_message)
builder.add_node("classify_message", classify_message)
builder.add_node("decision_maker", decision_maker)
builder.add_node("human_feedback", human_feedback)
builder.add_node("ai_notification", ai_notification)
builder.add_node("end", end)

builder.add_edge(START, "process_message")
builder.add_edge("process_message", "classify_message")
builder.add_edge("classify_message", "decision_maker")
builder.add_conditional_edges(
    "decision_maker",
    lambda state: state["classification"],
    {
        "respond": "human_feedback",
        "notify": "ai_notification", 
        "ignore": "end"
    }
)
builder.add_edge("human_feedback", "end")
builder.add_edge("ai_notification", "end")
builder.add_edge("end", END)

# Set up memory
memory = InMemorySaver()

# Add
RUN_LOCAL = True
if RUN_LOCAL:
    graph = builder.compile()
else:
    graph = builder.compile(checkpointer=memory)

# View
# display(Image(graph.get_graph().draw_mermaid_png()))

# Input
"""
initial_input = {"input": "C09A2NZNEBS|U0999D7H9M0|Can you sign the RR?"}

# Thread
thread = {"configurable": {"thread_id": "1"}}

# Run the graph until the first interruption
for event in graph.stream(initial_input, thread, stream_mode="updates"):
    print(event)
    print("\n")

import time
time.sleep(10)

# Continue the graph execution
for event in graph.stream(
    Command(resume="Ok i will sign it"),
    thread,
    stream_mode="updates",
):
    print(event)
    print("\n")
"""