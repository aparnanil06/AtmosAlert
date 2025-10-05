# backend/scheduler.py
import schedule
import time
from notifications import check_all_locations_and_alert, init_db

def job():
    try:
        check_all_locations_and_alert()
    except Exception as e:
        print(f"Error in scheduled job: {e}")

if __name__ == "__main__":
    # Initialize database on first run
    init_db()
    
    print("Air Quality Alert Scheduler started")
    print("Running checks every hour...")
    print("Press Ctrl+C to stop\n")
    
    # Schedule the job every hour
    schedule.every().hour.do(job)
    
    # Run once immediately on startup
    print("Running initial check...")
    job()
    
    # Keep running
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute if it's time to run