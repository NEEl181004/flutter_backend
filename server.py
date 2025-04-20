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

    # Create all necessary tables
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pending_bills (
            id SERIAL PRIMARY KEY,
            consumer_number VARCHAR(20),
            title VARCHAR(100),
            amount INTEGER,
            status VARCHAR(10) DEFAULT 'Unpaid'
        );
    """)
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
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS city_alerts (
    id SERIAL PRIMARY KEY,
    type VARCHAR(50) CHECK (type IN ('electricity', 'municipal')),
    message TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS polls (
    id SERIAL PRIMARY KEY,
    question TEXT NOT NULL,
    options TEXT NOT NULL,  -- Comma-separated list of options
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    date DATE NOT NULL,
    time TIME NOT NULL,
    location TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS news (
    id SERIAL PRIMARY KEY,
    headline VARCHAR(255) NOT NULL,
    date VARCHAR(50) NOT NULL,
    time VARCHAR(50) NOT NULL
        );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS hospitals (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
        );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS doctors (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    specialization TEXT,
    hospital_id INTEGER REFERENCES hospitals(id)
        );
    """)


    cursor.execute("""
    CREATE TABLE IF NOT EXISTS appointments (
    id SERIAL PRIMARY KEY,               
    patient_name TEXT,
    hospital_name TEXT,               
    doctor_id INTEGER REFERENCES doctors(id),
    appointment_date DATE,
    appointment_time TEXT
        );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS medicine_orders (
    id SERIAL PRIMARY KEY,
    username TEXT NOT NULL,
    items TEXT NOT NULL,
    total_price NUMERIC(10,2) NOT NULL,
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
        occupied = [str(row[0]) for row in cursor.fetchall()]
        return jsonify({'slots': {location: occupied}}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/parking_slots', methods=['GET'])
def get_parking_slots():
    try:
        cursor.execute("SELECT slot_id, location FROM parking_slots WHERE is_occupied = FALSE")
        rows = cursor.fetchall()
        slots_by_location = {}

        for slot_id, location in rows:
            slot_str = str(slot_id)
            if location not in slots_by_location:
                slots_by_location[location] = []
            slots_by_location[location].append(slot_str)

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

        cursor.execute("SELECT DISTINCT location FROM parking_slots")
        all_locations = cursor.fetchall()

        parking_areas = []
        for location in all_locations:
            location_name = location[0]
            occupied_spots = next((row[1] for row in occupied_rows if row[0] == location_name), 0)
            available_spots = 40 - occupied_spots
            parking_areas.append({
                'name': location_name,
                'spots': f'{available_spots} spots available',
            })

        return jsonify(parking_areas), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@app.route('/update_alert', methods=['POST'])
def update_alert():
    data = request.get_json()
    alert_type = data.get('type')  # "electricity" or "municipal"
    message = data.get('message')

    if alert_type not in ['electricity', 'municipal']:
        return jsonify({'status': 'error', 'message': 'Invalid alert type'}), 400

    try:
        cursor.execute("""
            DELETE FROM city_alerts WHERE type = %s
        """, (alert_type,))
        cursor.execute("""
            INSERT INTO city_alerts (type, message) VALUES (%s, %s)
        """, (alert_type, message))
        conn.commit()
        return jsonify({'status': 'success', 'message': f'{alert_type.capitalize()} alert updated'})
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
@app.route('/get_alerts', methods=['GET'])
def get_alerts():
    try:
        cursor.execute("""
            SELECT type, message, created_at FROM city_alerts
        """)
        records = cursor.fetchall()
        response = {
            'electricity': None,
            'municipal': None
        }
        for r in records:
            if r[0] == 'electricity':
                response['electricity'] = {
                    'message': r[1],
                    'created_at': r[2].strftime('%Y-%m-%d %H:%M')
                }
            elif r[0] == 'municipal':
                response['municipal'] = {
                    'message': r[1],
                    'created_at': r[2].strftime('%Y-%m-%d %H:%M')
                }
        return jsonify(response), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
@app.route('/get_polls', methods=['GET'])
def get_polls():
    try:
        cursor.execute("SELECT id, question, options FROM polls")
        polls = cursor.fetchall()
        response = []
        for poll in polls:
            poll_data = {
                'id': poll[0],
                'question': poll[1],
                'options': poll[2].split(',')  # Assuming options are stored as comma-separated strings
            }
            response.append(poll_data)
        return jsonify(response), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
@app.route('/add_poll', methods=['POST'])
def add_poll():
    data = request.get_json()
    question = data.get('question')
    options = data.get('options')  # Expected to be a list of options

    if not question or not options:
        return jsonify({'status': 'error', 'message': 'Question and options are required'}), 400

    try:
        options_str = ','.join(options)  # Convert options list to comma-separated string
        cursor.execute("INSERT INTO polls (question, options) VALUES (%s, %s)", (question, options_str))
        conn.commit()
        return jsonify({'status': 'success', 'message': 'Poll added successfully'}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
@app.route('/add_event', methods=['POST'])
def add_event():
    data = request.get_json()
    title = data.get('title')
    date = data.get('date')
    time = data.get('time')
    location = data.get('location')

    if not all([title, date, time, location]):
        return jsonify({'status': 'error', 'message': 'All fields are required'}), 400

    try:
        cursor.execute("""
            INSERT INTO events (title, date, time, location) 
            VALUES (%s, %s, %s, %s)
        """, (title, date, time, location))
        conn.commit()
        return jsonify({'status': 'success', 'message': 'Event added successfully'}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/get_events', methods=['GET'])
def get_events():
    try:
        cursor.execute("SELECT title, date, time, location FROM events ORDER BY date")
        records = cursor.fetchall()
        events = []
        for r in records:
            events.append({
                'title': r[0],
                'date': r[1].strftime('%Y-%m-%d'),
                'time': r[2].strftime('%H:%M'),
                'location': r[3]
            })
        return jsonify({'events': events}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
@app.route('/add_news', methods=['POST'])
def add_news():
    data = request.get_json()
    headline = data.get('headline')
    date = data.get('date')  # Expecting format: 'YYYY-MM-DD'
    time = data.get('time')  # Expecting format: 'HH:MM' (24-hour format)
    
    if not all([headline, date, time]):
        return jsonify({'status': 'error', 'message': 'All fields are required'}), 400

    try:
        cursor.execute("""
            INSERT INTO news (headline, date, time)
            VALUES (%s, %s, %s)
        """, (headline, date, time))
        conn.commit()
        return jsonify({'status': 'success', 'message': 'News added successfully'}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/get_news', methods=['GET'])
def get_news():
    try:
        cursor.execute("SELECT headline, date, time FROM news ORDER BY date DESC")
        records = cursor.fetchall()
        news = []
        for r in records:
            news.append({
                'headline': r[0],
                'date': r[1],
                'time': r[2]
            })
        return jsonify({'news': news}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    

@app.route('/get_hospitals', methods=['GET'])
def get_hospitals():
    cursor.execute("SELECT id, name FROM hospitals")
    hospitals = cursor.fetchall()
    return jsonify([{"id": h[0], "name": h[1]} for h in hospitals])

@app.route('/get_doctors/<hospital_name>', methods=['GET'])
def get_doctors(hospital_name):
    cursor.execute("SELECT id FROM hospitals WHERE name=%s", (hospital_name,))
    hospital = cursor.fetchone()
    if hospital:
        cursor.execute("SELECT id, name FROM doctors WHERE hospital_id=%s", (hospital[0],))
        doctors = cursor.fetchall()
        return jsonify([{"id": d[0], "name": d[1]} for d in doctors])
    return jsonify([])

@app.route('/book_appointment', methods=['POST'])
def book_appointment():
    data = request.json
    cursor.execute("""
        INSERT INTO appointments (patient_name, hospital_name, doctor_id, appointment_date, appointment_time)
        VALUES (%s, %s, %s, %s, %s)
    """, (data['patient_name'], data['hospital_name'], data['doctor_id'], data['date'], data['time']))
    conn.commit()
    return jsonify({"message": "Appointment booked successfully"})

@app.route('/add_hospital', methods=['POST'])
def add_hospital():
    try:
        data = request.get_json()
        name = data.get('name')

        if not name:
            return jsonify({"error": "Missing 'name' in request"}), 400

        cursor.execute("INSERT INTO hospitals (name) VALUES (%s)", (name,))
        conn.commit()
        return jsonify({"message": "Hospital added"}), 200

    except Exception as e:
        print("Error occurred:", str(e))
        return jsonify({"error": "Internal server error"}), 500
    
@app.route('/add_doctor',methods=['POST'])    
def add_doctor():
    try:
        # Parse incoming JSON data
        data = request.json
        hospital_name = data.get('hospital_name')
        doctor_name = data.get('name')
        specialization = data.get('specialization')

        if not hospital_name or not doctor_name or not specialization:
            return jsonify({"error": "Missing required fields"}), 400

        # Find the hospital by name
        cursor.execute("SELECT id FROM hospitals WHERE name=%s", (hospital_name,))
        hospital = cursor.fetchone()

        if hospital:
            # Insert the doctor into the database
            cursor.execute(
                "INSERT INTO doctors (name, specialization, hospital_id) VALUES (%s, %s, %s)",
                (doctor_name, specialization, hospital[0])
            )
            conn.commit()
            return jsonify({"message": "Doctor added successfully"}), 201
        else:
            return jsonify({"error": "Hospital not found"}), 404

    except psycopg2.DatabaseError as e:
        conn.rollback()  # Rollback in case of error
        return jsonify({"error": f"Database error: {str(e)}"}), 500

    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500

@app.route('/order_medicine', methods=['POST'])
def order_medicine():
    try:
        # Parse the incoming JSON data
        data = request.json
        username = data.get('username')
        items = data.get('items')
        total_price = data.get('total_price')

        # Validate the incoming data
        if not username or not isinstance(username, str):
            return jsonify({"error": "Missing or invalid 'username'"}), 400
        if not items or not isinstance(items, list) or not all(isinstance(i, str) for i in items):
            return jsonify({"error": "Missing or invalid 'items' (must be a list of strings)"}), 400
        if total_price is None or not isinstance(total_price, (int, float)):
            return jsonify({"error": "Missing or invalid 'total_price'"}), 400

        # Connect to the database

        # Insert the order into the database
        cursor.execute("""
            INSERT INTO medicine_orders (username, items, total_price)
            VALUES (%s, %s, %s) RETURNING id;
        """, (username, ', '.join(items), total_price))
        order_id = cursor.fetchone()[0]

        # Commit the transaction and close the cursor and connection
        conn.commit()
        cursor.close()
        conn.close()

        # Return a success message with the order ID
        return jsonify({"message": "Order placed successfully", "order_id": order_id}), 201

    except Exception as e:
        # Handle any unexpected errors
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

# Route to view order history
@app.route('/order_history/<string:username>', methods=['GET'])
def view_order_history(username):
    cursor.execute("""
        SELECT id, items, total_price, timestamp 
        FROM medicine_orders WHERE username = %s ORDER BY timestamp DESC;
    """, (username,))
    
    orders = cursor.fetchall()
    cursor.close()
    conn.close()

    if orders:
        return jsonify({"orders": orders}), 200
    else:
        return jsonify({"message": "No orders found for this user."}), 404
    
@app.route('/order_history/<string:username>', methods=['GET'])
def view_order_history(username):
    try:
        # Connect to the databas

        # Execute the SQL query to fetch orders
        cursor.execute("""
            SELECT id, items, total_price, timestamp 
            FROM medicine_orders WHERE username = %s ORDER BY timestamp DESC;
        """, (username,))

        # Fetch all orders from the query
        orders = cursor.fetchall()

        # Close the cursor and connection
        cursor.close()
        conn.close()

        if orders:
            # Format orders into a list of dictionaries
            formatted_orders = [
                {
                    "order_id": order[0],
                    "items": order[1],
                    "total_price": order[2],
                    "timestamp": order[3]
                }
                for order in orders
            ]
            return jsonify({"orders": formatted_orders}), 200
        else:
            return jsonify({"message": "No orders found for this user."}), 404

    except Exception as e:
        # Handle any exceptions, like database errors
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500



# ===================== MAIN =====================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
