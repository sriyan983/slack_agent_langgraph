#!/bin/bash

# Message Processor Cron Management Script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRON_SCRIPT="$SCRIPT_DIR/cron_message_processor.py"
LOG_FILE="$SCRIPT_DIR/message_processor_cron.log"
PID_FILE="$SCRIPT_DIR/message_processor_cron.pid"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}  Message Processor Cron Manager${NC}"
    echo -e "${BLUE}================================${NC}"
}

# Check if Python script exists
if [ ! -f "$CRON_SCRIPT" ]; then
    print_error "Cron script not found: $CRON_SCRIPT"
    exit 1
fi

# Function to start the cron
start_cron() {
    print_header
    print_status "Starting Message Processor Cron..."
    
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            print_warning "Cron is already running with PID: $PID"
            return 1
        else
            print_warning "Removing stale PID file"
            rm -f "$PID_FILE"
        fi
    fi
    
    # Start the cron in background
    nohup python3 "$CRON_SCRIPT" --interval 30 > "$LOG_FILE" 2>&1 &
    PID=$!
    echo $PID > "$PID_FILE"
    
    print_status "Cron started with PID: $PID"
    print_status "Log file: $LOG_FILE"
    print_status "PID file: $PID_FILE"
    print_status "Use './run_cron.sh status' to check status"
}

# Function to stop the cron
stop_cron() {
    print_header
    print_status "Stopping Message Processor Cron..."
    
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            print_status "Sending SIGTERM to PID: $PID"
            kill $PID
            
            # Wait for graceful shutdown
            for i in {1..10}; do
                if ! ps -p $PID > /dev/null 2>&1; then
                    print_status "Cron stopped successfully"
                    rm -f "$PID_FILE"
                    return 0
                fi
                sleep 1
            done
            
            # Force kill if still running
            print_warning "Force killing process..."
            kill -9 $PID
            rm -f "$PID_FILE"
            print_status "Cron force stopped"
        else
            print_warning "Process not running, removing stale PID file"
            rm -f "$PID_FILE"
        fi
    else
        print_warning "PID file not found, cron may not be running"
    fi
}

# Function to check status
status_cron() {
    print_header
    
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            print_status "Cron is running with PID: $PID"
            print_status "Log file: $LOG_FILE"
            
            # Show recent log entries
            if [ -f "$LOG_FILE" ]; then
                echo ""
                print_status "Recent log entries:"
                tail -n 10 "$LOG_FILE"
            fi
        else
            print_error "Cron is not running (stale PID file)"
            rm -f "$PID_FILE"
        fi
    else
        print_warning "Cron is not running (no PID file)"
    fi
}

# Function to show logs
show_logs() {
    if [ -f "$LOG_FILE" ]; then
        print_status "Showing logs (press Ctrl+C to exit):"
        tail -f "$LOG_FILE"
    else
        print_error "Log file not found: $LOG_FILE"
    fi
}

# Function to restart the cron
restart_cron() {
    print_header
    print_status "Restarting Message Processor Cron..."
    stop_cron
    sleep 2
    start_cron
}

# Main script logic
case "$1" in
    start)
        start_cron
        ;;
    stop)
        stop_cron
        ;;
    restart)
        restart_cron
        ;;
    status)
        status_cron
        ;;
    logs)
        show_logs
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs}"
        echo ""
        echo "Commands:"
        echo "  start   - Start the message processor cron"
        echo "  stop    - Stop the message processor cron"
        echo "  restart - Restart the message processor cron"
        echo "  status  - Show status and recent logs"
        echo "  logs    - Show live logs (tail -f)"
        echo ""
        echo "The cron will run every 30 seconds by default."
        exit 1
        ;;
esac 