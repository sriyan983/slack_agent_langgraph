#!/usr/bin/env python3
"""
Cron job script to run message processor every 30 seconds
"""

import time
import sys
import os
import signal
from datetime import datetime
import logging

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from message_processor.message_processor import MessageProcessor

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('message_processor_cron.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MessageProcessorCron:
    def __init__(self, interval_seconds=30):
        self.interval_seconds = interval_seconds
        self.processor = MessageProcessor()
        self.running = True
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False
    
    def run_single_cycle(self):
        """Run a single processing cycle"""
        try:
            logger.info("🔄 Starting message processing cycle...")
            
            # Process pending messages
            processed_count = self.processor.process_pending_messages(batch_size=5)
            
            if processed_count > 0:
                logger.info(f"✅ Processed {processed_count} messages in this cycle")
            else:
                logger.info("ℹ️ No messages to process in this cycle")
                
            return True
            
        except Exception as e:
            logger.error(f"❌ Error in processing cycle: {e}")
            return False
    
    def run_continuous(self):
        """Run the message processor continuously with specified interval"""
        logger.info(f"🚀 Starting Message Processor Cron (interval: {self.interval_seconds}s)")
        logger.info("Press Ctrl+C to stop")
        
        cycle_count = 0
        
        while self.running:
            try:
                cycle_count += 1
                start_time = datetime.now()
                
                logger.info(f"📊 Cycle #{cycle_count} started at {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
                
                # Run processing cycle
                success = self.run_single_cycle()
                
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                if success:
                    logger.info(f"✅ Cycle #{cycle_count} completed in {duration:.2f}s")
                else:
                    logger.warning(f"⚠️ Cycle #{cycle_count} completed with errors in {duration:.2f}s")
                
                # Sleep until next cycle (account for processing time)
                if self.running:
                    sleep_time = max(0, self.interval_seconds - duration)
                    if sleep_time > 0:
                        logger.info(f"😴 Sleeping for {sleep_time:.2f}s until next cycle...")
                        time.sleep(sleep_time)
                    else:
                        logger.warning(f"⚠️ Processing took longer than interval ({duration:.2f}s > {self.interval_seconds}s)")
                
            except KeyboardInterrupt:
                logger.info("🛑 Received keyboard interrupt, shutting down...")
                self.running = False
                break
            except Exception as e:
                logger.error(f"❌ Unexpected error in main loop: {e}")
                if self.running:
                    logger.info(f"😴 Sleeping for {self.interval_seconds}s before retry...")
                    time.sleep(self.interval_seconds)
        
        logger.info("👋 Message Processor Cron stopped")

def main():
    """Main function to run the cron job"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run message processor as a cron job")
    parser.add_argument(
        "--interval", 
        type=int, 
        default=30, 
        help="Interval between processing cycles in seconds (default: 30)"
    )
    parser.add_argument(
        "--batch-size", 
        type=int, 
        default=5, 
        help="Number of messages to process per cycle (default: 5)"
    )
    
    args = parser.parse_args()
    
    # Create and run the cron job
    cron = MessageProcessorCron(interval_seconds=args.interval)
    
    # Override batch size if specified
    if args.batch_size != 5:
        cron.processor.batch_size = args.batch_size
        logger.info(f"📦 Batch size set to {args.batch_size}")
    
    try:
        cron.run_continuous()
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 