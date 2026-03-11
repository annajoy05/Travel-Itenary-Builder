import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
import os
import csv
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')

def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    # Create tables based on architecture (PostgreSQL syntax)
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id SERIAL PRIMARY KEY,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            preferences TEXT
        );

        CREATE TABLE IF NOT EXISTS trip_experiences (
            trip_id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(user_id),
            destination TEXT,
            trip_date TEXT,
            companion_type TEXT,
            stay_name TEXT,
            stay_price REAL,
            stay_rating REAL,
            total_expense REAL
        );

        CREATE TABLE IF NOT EXISTS places_visited (
            place_id SERIAL PRIMARY KEY,
            trip_id INTEGER REFERENCES trip_experiences(trip_id),
            place_order INTEGER,
            place_name TEXT,
            place_rating REAL,
            entry_fee REAL,
            distance_from_prev REAL,
            travel_method TEXT,
            travel_cost REAL,
            travel_rating REAL,
            experience_review TEXT
        );
    ''')
    
    conn.commit()
    c.close()

    # Load dataset
    load_csv_dataset(conn)

    conn.close()

def load_csv_dataset(conn):
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM trip_experiences')
    if c.fetchone()[0] > 0:
        c.close()
        return

    print("Loading dataset into database... This may take a moment.")
    trips_data = {}
    places_batch = []
    trip_place_counts = {}
    
    csv_path = os.path.join(os.path.dirname(__file__), 'travel_dataset.csv')
    if not os.path.exists(csv_path):
        print(f"Dataset file {csv_path} not found.")
        c.close()
        return
        
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            trip_id = int(row['trip_id'])
            
            if trip_id not in trips_data:
                trips_data[trip_id] = (
                    trip_id,
                    None, # user_id
                    row['destination'],
                    row['trip_date'],
                    row['companion_type'],
                    row['stay_name'],
                    float(row['stay_price']) if row['stay_price'] else 0.0,
                    float(row['stay_rating']) if row['stay_rating'] else 0.0,
                    float(row['total_expense']) if row['total_expense'] else 0.0
                )
            
            place_order = trip_place_counts.get(trip_id, 0)
            trip_place_counts[trip_id] = place_order + 1
            
            places_batch.append((
                trip_id,
                place_order,
                row['place_name'],
                float(row['place_rating']) if row['place_rating'] else 0.0,
                float(row['entry_fee']) if row['entry_fee'] else 0.0,
                float(row['distance_from_prev']) if row['distance_from_prev'] else 0.0,
                row['travel_method'],
                float(row['travel_cost']) if row['travel_cost'] else 0.0,
                float(row['travel_rating']) if row['travel_rating'] else 0.0,
                row['experience_review']
            ))

    execute_values(
        c,
        '''INSERT INTO trip_experiences 
           (trip_id, user_id, destination, trip_date, companion_type, stay_name, stay_price, stay_rating, total_expense) 
           VALUES %s ON CONFLICT (trip_id) DO NOTHING''',
        list(trips_data.values())
    )
    
    execute_values(
        c,
        '''INSERT INTO places_visited 
           (trip_id, place_order, place_name, place_rating, entry_fee, distance_from_prev, travel_method, travel_cost, travel_rating, experience_review) 
           VALUES %s''',
        places_batch
    )
    
    # Update sequence
    c.execute("SELECT setval('trip_experiences_trip_id_seq', (SELECT MAX(trip_id) FROM trip_experiences));")
    
    conn.commit()
    c.close()
    print("Dataset loaded successfully.")

if __name__ == '__main__':
    init_db()
    print("PostgreSQL Database initialized successfully.")
