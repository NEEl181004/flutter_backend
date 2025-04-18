from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
import os
from datetime import date

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
    # ✅ Add this after existing table creation in DB setup:
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

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    try:
        cursor.execute("SELECT * FROM users WHERE email=%s AND password=%s", (email, password))
        user = cursor.fetchone()
        if user:
            return jsonify({'status': 'success'}), 200
        else:
            return jsonify({'status': 'invalid_credentials'}), 401
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


@app.route('/pay_bill', methods=['POST'])
def pay_bill():
    data = request.get_json()
    bill_id = data.get('bill_id')
    consumer_number = data.get('consumer_number')
    title = data.get('title')
    amount = data.get('amount')

    try:
        # Insert into payment history
        cursor.execute("""
            INSERT INTO payment_history (consumer_number, title, amount, payment_date)
            VALUES (%s, %s, %s, %s)
        """, (consumer_number, title, amount, date.today()))

        # Delete from pending bills
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
    
@app.route('/book_parking', methods=['POST'])
def book_parking():
    data = request.get_json()
    email = data.get('email')
    location = data.get('location')
    date_str = data.get('date')  # e.g. "2025-04-20"
    time = data.get('time')      # e.g. "10:30 AM"
    slot = data.get('slot')      # e.g. "A5"

    try:
        cursor.execute("""
            INSERT INTO parking_tickets (user_email, location, date, time, slot, payment_status)
            VALUES (%s, %s, %s, %s, %s, 'Paid')
        """, (email, location, date_str, time, slot))
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



# ===================== MAIN =====================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
