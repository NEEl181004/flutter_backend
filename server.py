from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
import os

app = Flask(__name__)
CORS(app)

# Connect to PostgreSQL using environment variables
conn = psycopg2.connect(
    host=os.getenv('localhost'),
    database=os.getenv('postgres'),
    user=os.getenv('postgres'),
    password=os.getenv('31998369'),
    port=os.getenv('DB_PORT', 6543)
)
cursor = conn.cursor()

@app.route('/signup', methods=['POST'])
def signup():
    data = request.json
    email = data['email']
    password = data['password']

    try:
        cursor.execute("INSERT INTO users (email, password) VALUES (%s, %s)", (email, password))
        conn.commit()
        return jsonify({'status': 'success'}), 200
    except:
        conn.rollback()
        return jsonify({'status': 'user_exists'}), 400

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data['email']
    password = data['password']

    cursor.execute("SELECT * FROM users WHERE email=%s AND password=%s", (email, password))
    user = cursor.fetchone()

    if user:
        return jsonify({'status': 'success'}), 200
    else:
        return jsonify({'status': 'invalid_credentials'}), 401

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)  # Port doesn't matter on Render
