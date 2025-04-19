from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
import os
from datetime import date, datetime

app = Flask(__name__)
CORS(app)

# PostgreSQL connection using Render environment variables
try:
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST'),
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        port=os.getenv('DB_PORT', 5432)
    )
    cursor = conn.cursor()

    # Create users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        );
    """)

    # Create admins table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        );
    """)

    # Create pending_bills table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pending_bills (
            id SERIAL PRIMARY KEY,
            consumer_number VARCHAR(20),
            title VARCHAR(100),
            amount INTEGER,
            status VARCHAR(10) DEFAULT 'Unpaid'
        );
    """)

    # Create payment_history table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payment_history (
            id SERIAL PRIMARY KEY,
            consumer_number VARCHAR(20),
            title VARCHAR(100),
            amount INTEGER,
            payment_date DATE DEFAULT CURRENT_DATE
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS parking_tickets (
            id SERIAL PRIMARY KEY,
            user_email TEXT NOT NULL,
            location TEXT NOT NULL,
            date DATE NOT NULL,
            time TEXT NOT NULL,
            slot TEXT NOT NULL,
            payment_status TEXT DEFAULT 'Paid',
            booking_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS parking_slots (
            id SERIAL PRIMARY KEY,
            slot_id VARCHAR(50) NOT NULL,
            location VARCHAR(100),
            is_occupied BOOLEAN DEFAULT FALSE,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            
        );
    """)

    conn.commit()
    print("✅ Connected to DB and ensured all tables exist")
except Exception as e:
    print("❌ Database connection/setup failed:", e)

# ===================== AUTH ROUTES =====================

@app.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    try:
        cursor.execute("INSERT INTO users (email, password) VALUES (%s, %s)", (email, password))
        conn.commit()
        return jsonify({'status': 'success'}), 200
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        return jsonify({'status': 'user_exists'}), 400
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

ADMIN_EMAIL = 'smartcityportal941@gmail.com'
ADMIN_PASSWORD = 'Admin@123'
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    # Admin check
    if email == ADMIN_EMAIL and password == ADMIN_PASSWORD:
        return jsonify({'status': 'admin'}), 200

    try:
        cursor.execute("SELECT * FROM users WHERE email=%s AND password=%s", (email, password))
        user = cursor.fetchone()
        if user:
            return jsonify({'status': 'success'}), 200
        else:
            return jsonify({'status': 'invalid_credentials'}), 401
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/validate_email', methods=['POST'])
def validate_email():
    data = request.get_json()
    email = data.get('email')

    try:
        cursor.execute("SELECT 1 FROM users WHERE email=%s", (email,))
        user_exists = cursor.fetchone() is not None
        return jsonify({'valid': user_exists}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ===================== BILL ROUTES =====================

@app.route('/bills/<consumer_number>', methods=['GET'])
def get_pending_bills(consumer_number):
    try:
        cursor.execute("""
            SELECT id, title, amount 
            FROM pending_bills 
            WHERE consumer_number = %s AND status = 'Unpaid'
        """, (consumer_number,))
        bills = cursor.fetchall()
        result = [{'id': b[0], 'title': b[1], 'amount': b[2]} for b in bills]
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/add-bill', methods=['POST'])
def add_bill():
    data = request.get_json()
    consumer_number = data.get('consumer_number')
    title = data.get('title')
    amount = data.get('amount')

    try:
        cursor.execute("""
            INSERT INTO pending_bills (consumer_number, title, amount)
            VALUES (%s, %s, %s)
        """, (consumer_number, title, amount))
        conn.commit()
        return jsonify({'status': 'success', 'message': 'Bill added successfully'}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/pay_bill', methods=['POST'])
def pay_bill():
    data = request.get_json()
    bill_id = data.get('bill_id')
    consumer_number = data.get('consumer_number')
    title = data.get('title')
    amount = data.get('amount')

    try:
        cursor.execute("""
            INSERT INTO payment_history (consumer_number, title, amount, payment_date)
            VALUES (%s, %s, %s, %s)
        """, (consumer_number, title, amount, date.today()))

        cursor.execute("DELETE FROM pending_bills WHERE id = %s", (bill_id,))
        conn.commit()
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/payment_history/<consumer_number>', methods=['GET'])
def get_payment_history(consumer_number):
    try:
        cursor.execute("""
            SELECT title, amount, payment_date 
            FROM payment_history 
            WHERE consumer_number = %s
            ORDER BY payment_date DESC
        """, (consumer_number,))
        records = cursor.fetchall()
        result = [{'title': r[0], 'amount': r[1], 'date': r[2].strftime('%Y-%m-%d')} for r in records]
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ===================== PARKING ROUTES =====================

@app.route('/book_parking', methods=['POST'])
def book_parking():
    data = request.get_json()
    email = data.get('email')
    location = data.get('location')
    date_str = data.get('date')
    time = data.get('time')
    slot = data.get('slot')

    try:
        cursor.execute("""
            INSERT INTO parking_tickets (user_email, location, date, time, slot, payment_status)
            VALUES (%s, %s, %s, %s, %s, 'Paid')
        """, (email, location, date_str, time, slot))
        # Update slot to marked as occupied
        cursor.execute("""
            UPDATE parking_slots
            SET is_occupied = TRUE
            WHERE slot_id = %s AND location = %s
        """, (slot, location))
        conn.commit()
        return jsonify({'status': 'success', 'message': 'Ticket booked successfully'}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
@app.route('/my_tickets/<email>', methods=['GET'])
def get_my_tickets(email):
    try:
        cursor.execute("""
            SELECT location, date, time, slot, payment_status, booking_timestamp
            FROM parking_tickets
            WHERE user_email = %s
            ORDER BY booking_timestamp DESC
        """, (email,))
        records = cursor.fetchall()
        result = [{
            'location': r[0],
            'date': r[1].strftime('%Y-%m-%d'),
            'time': r[2],
            'slot': r[3],
            'payment_status': r[4],
            'booked_on': r[5].strftime('%Y-%m-%d %H:%M')
        } for r in records]
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/occupied_slots', methods=['POST'])
def get_occupied_slots():
    data = request.get_json()
    location = data['location']
    date_str = data['date']

    try:
        cursor.execute("""
            SELECT slot FROM parking_tickets
            WHERE location = %s AND date = %s
              AND ABS(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - booking_timestamp)))/3600 < 1
        """, (location, date_str))
        occupied = [row[0] for row in cursor.fetchall()]
        return jsonify({'occupied_slots': occupied}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@app.route('/parking_slots', methods=['GET'])
def get_parking_slots():
    try:
        cursor.execute("SELECT slot_id, location FROM parking_slots WHERE is_occupied = FALSE")
        rows = cursor.fetchall()
        slots_by_location = {}

        for slot_id, location in rows:
            if location not in slots_by_location:
                slots_by_location[location] = []
            slots_by_location[location].append(slot_id)

        return jsonify({'slots': slots_by_location}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@app.route('/parking/add', methods=['POST'])
def add_parking_slot():
    data = request.get_json()
    slot_id = data.get('slot_id')
    location = data.get('location')

    if not slot_id or not location:
        return jsonify({'error': 'Missing data'}), 400

    try:
        cursor.execute("""
            INSERT INTO parking_slots (slot_id, location, is_occupied, timestamp)
            VALUES (%s, %s, FALSE, NOW())
        """, (slot_id, location))
        conn.commit()
        return jsonify({'message': 'Slot added'}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    
@app.route('/parking_areas', methods=['GET'])
def get_parking_areas():
    try:
        cursor.execute("""
            SELECT location, COUNT(*) 
            FROM parking_slots 
            WHERE is_occupied = TRUE 
            GROUP BY location
        """)
        occupied_rows = cursor.fetchall()
        
        # Get all unique parking locations
        cursor.execute("SELECT DISTINCT location FROM parking_slots")
        all_locations = cursor.fetchall()
        
        parking_areas = []
        
        for location in all_locations:
            location_name = location[0]
            
            # Get the number of occupied spots for the location
            occupied_spots = next((row[1] for row in occupied_rows if row[0] == location_name), 0)
            
            # Calculate available spots (30 total - occupied spots)
            available_spots = 30 - occupied_spots
            
            parking_areas.append({
                'name': location_name,
                'spots': f'{available_spots} spots available',
            })
        
        return jsonify(parking_areas), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ===================== MAIN =====================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
