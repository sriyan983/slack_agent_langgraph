# Slack Auto-Responder Agent – LangGraph Certification Project

## 📖 Overview
This project is an **assignment work** for the **LangGraph Certification** and reflects its **practical use** in building an automated Slack responder agent.

The goal is to:
- Read incoming Slack messages
- Classify them into:
  - **Ignore** – No action taken
  - **Notify** – Use an LLM to respond meaningfully (with history)
  - **Respond** – HITL (Human-in-the-Loop) state awaiting manual feedback

---

## 🧩 Architecture & Flow

**Project Structure**  
```
slack_agents/
  agent_graph/           # LangGraph workflows
  api/                   # API endpoints
  db/                    # Database scripts
  message_processor/     # CRON processing logic
  slack_pipeline/        # Slack message ingestion
  ui/                    # Streamlit dashboard
  run_slack_pipeline.py  # Entry point for Slack listener
  run_cron.sh            # CRON control script
  requirements.txt
  .env                   # Environment variables
```

**Graph Workflow**  
![LangGraph Studio](images/langgraph_studio.png)

- **Ignore** → No further action
- **Notify** → LLM generates a response using historical context
- **Respond** → Message enters HITL state, waits for human feedback via the dashboard

**Dashboard (Streamlit)**  
![Dashboard](images/dashboard.png)

- Displays all processed messages
- Filters to **Respond** type for HITL feedback
- Allows entering a reply which is then sent back to Slack

**HITL Interaction Example**  
![Slack Agent in Action](images/slack_agent_in_action.png)

**API in Action**  
![API in Action](images/api_in_action.png)

**State Management**
- Uses **LangGraph checkpoints** to store workflow state
- Resumes processing whenever a human interacts via the dashboard

**Data Flow**
1. `slack_pipeline` reads messages and stores them in **PostgreSQL**
2. A **CRON job** runs every 30 seconds to process new messages
3. Graph decides to ignore, notify, or request HITL
4. Dashboard resumes HITL states and posts responses back to Slack
5. All events are logged in the database and visible in the dashboard

---

## 🚀 Slack App Setup

### 1️⃣ Create & Configure Slack App
1. Go to **Slack API → Your Apps → Create New App → From Scratch**
2. Enable **Socket Mode**:
   - In left menu → *Socket Mode* → Enable
   - Generate App-Level Token → add scope `connections:write` → Save
3. **Bot Token Scopes** (OAuth & Permissions):
   - `app_mentions:read`
   - `channels:read`
   - `channels:history`
   - `groups:history`
   - `im:history`
   - `mpim:history`
   - `chat:write`
4. Install App to Workspace → copy **Bot User OAuth Token** (xoxb-…)
5. Invite bot to desired channels:

---

### 2️⃣ Event Subscriptions
Even in Socket Mode, you must enable this:
- Go to **Event Subscriptions** → Enable
- Subscribe to bot events:
  - `message.channels`
  - `message.groups`
  - `message.im`
  - `message.mpim`
- Save changes

---

### 3️⃣ (Optional) Enable Delete Capability
To allow the bot to delete messages:
- Add `chat:delete` scope (and optionally `chat:write.public`)
- Save changes, reinstall the app, and update token in `.env`

---

## 🛠 Installation

You can use **Docker** for each module:
- `slack_pipeline`
- `message_processor` (CRON)
- `graph_api`
- `dashboard`

**Or** use a Python virtual environment:

```bash
python3 -m venv langgraph_env
source langgraph_env/bin/activate
pip install -r requirements.txt
```

(See requirements.txt for all packages.)

```bash
# Start the cron
./run_cron.sh start

# Check status
./run_cron.sh status

# View live logs
./run_cron.sh logs

# Stop the cron
./run_cron.sh stop

# Restart the cron
./run_cron.sh restart
```

**Note:**
- Ensure `message-processor-cron.service` has the correct absolute paths.
- Logs are available at: `message_processor_cron.log`

**Setup Slack app and .env with:**
```
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
DATABASE_URL=postgresql://user:pass@host/db
```


