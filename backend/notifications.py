# backend/notifications.py
import os
import sqlite3
from datetime import datetime
from typing import List, Dict
from dotenv import load_dotenv
import requests
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

load_dotenv()
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
FROM_EMAIL = os.getenv("FROM_EMAIL", "alerts@airquality.app")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8090")

DB_PATH = "notifications.db"

# ============ Database Setup ============
def init_db():
    """Create tables if they don't exist"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Users table
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            active INTEGER DEFAULT 1
        )
    """)
    
    # Monitored locations table
    c.execute("""
        CREATE TABLE IF NOT EXISTS monitored_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            location_type TEXT NOT NULL,
            location_value TEXT NOT NULL,
            threshold_aqi INTEGER DEFAULT 100,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    
    # Alert history table
    c.execute("""
        CREATE TABLE IF NOT EXISTS alert_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            location_id INTEGER NOT NULL,
            aqi INTEGER NOT NULL,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (location_id) REFERENCES monitored_locations(id)
        )
    """)
    
    conn.commit()
    conn.close()
    print("Database initialized")

# ============ User Management ============
def add_user(email: str, location_type: str, location_value: str, threshold_aqi: int = 100) -> dict:
    """
    Add a new user and their monitored location
    location_type: 'zip', 'address', or 'coords'
    location_value: ZIP code, address string, or 'lat,lon'
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    try:
        # Insert or get user
        c.execute("INSERT OR IGNORE INTO users (email) VALUES (?)", (email,))
        c.execute("SELECT id FROM users WHERE email = ?", (email,))
        user_id = c.fetchone()[0]
        
        # Add monitored location
        c.execute("""
            INSERT INTO monitored_locations (user_id, location_type, location_value, threshold_aqi)
            VALUES (?, ?, ?, ?)
        """, (user_id, location_type, location_value, threshold_aqi))
        
        conn.commit()
        location_id = c.lastrowid
        
        return {
            "success": True,
            "user_id": user_id,
            "location_id": location_id,
            "message": f"Successfully registered {email} for alerts at {location_value}"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()

def get_all_monitored_locations() -> List[Dict]:
    """Get all active monitored locations with user info"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("""
        SELECT 
            ml.id, ml.user_id, u.email, ml.location_type, 
            ml.location_value, ml.threshold_aqi
        FROM monitored_locations ml
        JOIN users u ON ml.user_id = u.id
        WHERE u.active = 1
    """)
    
    locations = []
    for row in c.fetchall():
        locations.append({
            "location_id": row[0],
            "user_id": row[1],
            "email": row[2],
            "location_type": row[3],
            "location_value": row[4],
            "threshold_aqi": row[5]
        })
    
    conn.close()
    return locations

def record_alert(user_id: int, location_id: int, aqi: int):
    """Record that an alert was sent"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO alert_history (user_id, location_id, aqi)
        VALUES (?, ?, ?)
    """, (user_id, location_id, aqi))
    conn.commit()
    conn.close()

def was_alerted_recently(user_id: int, location_id: int, hours: int = 6) -> bool:
    """Check if user was alerted in the last N hours (avoid spam)"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT COUNT(*) FROM alert_history
        WHERE user_id = ? AND location_id = ?
        AND sent_at > datetime('now', '-{} hours')
    """.format(hours), (user_id, location_id))
    count = c.fetchone()[0]
    conn.close()
    return count > 0

# ============ Air Quality Checking ============
def check_aqi_for_location(location_type: str, location_value: str) -> dict:
    """Query your backend API for AQI data"""
    try:
        if location_type == "zip":
            params = {"zip": location_value}
        elif location_type == "address":
            params = {"address": location_value}
        else:  # coords
            lat, lon = location_value.split(",")
            params = {"lat": float(lat), "lon": float(lon)}
        
        response = requests.get(f"{BACKEND_URL}/api/aqi", params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return {
                "success": True,
                "area_name": data.get("area_name"),
                "overall_aqi": data.get("overall_aqi"),
                "overall_category": data.get("overall_category"),
                "rows": data.get("rows")
            }
        else:
            return {"success": False, "error": f"API returned {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ============ Email Sending ============
def send_alert_email(email: str, area_name: str, aqi: int, category: dict, pollutants: list):
    """Send alert email via SendGrid"""
    
    if not SENDGRID_API_KEY:
        print(f"SENDGRID_API_KEY not set. Would send to {email}: AQI={aqi} at {area_name}")
        return True
    
    # Build email content
    pollutant_list = "\n".join([
        f"  • {p['pollutant'].upper()}: {p['latest_aqi']} AQI"
        for p in pollutants
    ])
    
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background-color: #ff6b6b; color: white; padding: 20px; text-align: center;">
            <h1>⚠️ Air Quality Alert</h1>
        </div>
        <div style="padding: 20px; background-color: #f8f9fa;">
            <h2>Air Quality in {area_name}</h2>
            <p style="font-size: 18px;">
                <strong>Current AQI: {aqi}</strong> - {category.get('label', 'Unknown')}
            </p>
            <div style="background-color: white; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <p>{category.get('message', 'Air quality may be unhealthy.')}</p>
            </div>
            <h3>Pollutant Levels:</h3>
            <pre style="background-color: white; padding: 15px; border-radius: 5px;">{pollutant_list}</pre>
            <p style="margin-top: 30px; font-size: 12px; color: #666;">
                You're receiving this because you signed up for air quality alerts.
            </p>
        </div>
    </body>
    </html>
    """
    
    message = Mail(
        from_email=FROM_EMAIL,
        to_emails=email,
        subject=f"⚠️ Air Quality Alert: {area_name} - AQI {aqi}",
        html_content=html_content
    )
    
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        print(f"Email sent to {email}: Status {response.status_code}")
        return True
    except Exception as e:
        print(f"Failed to send email to {email}: {e}")
        return False

# ============ Main Monitoring Loop ============
def check_all_locations_and_alert():
    """Main function: check all locations and send alerts if needed"""
    print(f"\n{'='*60}")
    print(f"Starting air quality check at {datetime.now()}")
    print(f"{'='*60}\n")
    
    locations = get_all_monitored_locations()
    print(f"Checking {len(locations)} monitored location(s)...\n")
    
    alerts_sent = 0
    
    for loc in locations:
        print(f"Checking {loc['location_value']} for {loc['email']}...")
        
        # Check if already alerted recently
        if was_alerted_recently(loc['user_id'], loc['location_id'], hours=6):
            print(f"  ⏭️  Skipped (already alerted in last 6 hours)")
            continue
        
        # Get AQI data
        aqi_data = check_aqi_for_location(loc['location_type'], loc['location_value'])
        
        if not aqi_data.get('success'):
            print(f"  ❌ Failed to get AQI: {aqi_data.get('error')}")
            continue
        
        overall_aqi = aqi_data.get('overall_aqi')
        
        if overall_aqi is None:
            print(f"  ⚠️  No AQI data available")
            continue
        
        print(f"  📊 Current AQI: {overall_aqi} (threshold: {loc['threshold_aqi']})")
        
        # Send alert if threshold exceeded
        if overall_aqi >= loc['threshold_aqi']:
            print(f"  🚨 ALERT! Sending notification...")
            
            success = send_alert_email(
                loc['email'],
                aqi_data.get('area_name', loc['location_value']),
                overall_aqi,
                aqi_data.get('overall_category'),
                aqi_data.get('rows', [])
            )
            
            if success:
                record_alert(loc['user_id'], loc['location_id'], overall_aqi)
                alerts_sent += 1
                print(f"  ✅ Alert sent successfully")
        else:
            print(f"  ✓ Air quality is good (below threshold)")
        
        print()
    
    print(f"{'='*60}")
    print(f"Check complete. Sent {alerts_sent} alert(s)")
    print(f"{'='*60}\n")

# ============ CLI Commands ============
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python notifications.py init                    # Initialize database")
        print("  python notifications.py add <email> <zip>       # Add user with ZIP code")
        print("  python notifications.py check                   # Run check now")
        print("  python notifications.py list                    # List all users")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "init":
        init_db()
    
    elif command == "add":
        if len(sys.argv) < 4:
            print("Usage: python notifications.py add <email> <zip_or_address>")
            sys.exit(1)
        
        email = sys.argv[2]
        location = sys.argv[3]
        
        # Auto-detect if ZIP or address
        location_type = "zip" if location.isdigit() else "address"
        
        result = add_user(email, location_type, location, threshold_aqi=100)
        print(result.get('message') if result['success'] else result.get('error'))
    
    elif command == "check":
        check_all_locations_and_alert()
    
    elif command == "list":
        locations = get_all_monitored_locations()
        print(f"\nMonitored Locations ({len(locations)}):\n")
        for loc in locations:
            print(f"  {loc['email']}: {loc['location_value']} (threshold: {loc['threshold_aqi']} AQI)")
        print()
    
    else:
        print(f"Unknown command: {command}")