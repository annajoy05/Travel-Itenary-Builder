from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import database
import bcrypt
import jwt
import os
import datetime
from functools import wraps
from engine import recommendation, mcts_selector, optimizer, planner
import psycopg2.errors
from authlib.integrations.flask_client import OAuth
import secrets
import string

app = Flask(__name__)
# In production, set the SECRET_KEY environment variable. 
# You can generate one with: python -c 'import os; print(os.urandom(24).hex())'
app.secret_key = os.environ.get('SECRET_KEY', 'super_secret_temporary_key')

# Allow OAuth testing over local HTTP
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# OAuth Setup
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.environ.get('GOOGLE_CLIENT_ID'),
    client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

# Initialize DB on startup (ensure tables exist)
database.init_db()

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.cookies.get('token')
        if not token:
            return jsonify({'message': 'Token is missing!'}), 401
        try:
            data = jwt.decode(token, app.secret_key, algorithms=["HS256"])
            # You could query user here and attach it
        except Exception as e:
            return jsonify({'message': 'Token is invalid!'}), 401
        return f(*args, **kwargs)
    return decorated

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    token = request.cookies.get('token')
    if not token:
        return redirect(url_for('login_page'))
    try:
        data = jwt.decode(token, app.secret_key, algorithms=["HS256"])
        conn = database.get_db_connection()
        c = conn.cursor(cursor_factory=database.RealDictCursor)
        c.execute('SELECT * FROM users WHERE user_id = %s', (data['user_id'],))
        user = c.fetchone()
        conn.close()
        if not user:
            return redirect(url_for('login_page'))
    except:
        return redirect(url_for('login_page'))
    
    # Check if a specific route section was requested
    route = request.args.get('route', 'welcome')

    return render_template('dashboard.html', user=user, route=route)

# API Endpoints
@app.route('/api/auth/register', methods=['POST'])
def api_register():
    data = request.json
    full_name = data.get('full_name')
    email = data.get('email')
    password = data.get('password')
    confirm_password = data.get('confirm_password')
    
    if not email or not password or not full_name or not confirm_password:
        return jsonify({'message': 'Please fill all fields'}), 400
        
    if password != confirm_password:
        return jsonify({'message': 'Passwords do not match'}), 400
        
    hashed_pwd = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    
    conn = database.get_db_connection()
    c = conn.cursor()
    try:
        c.execute('INSERT INTO users (full_name, email, password_hash) VALUES (%s, %s, %s)', (full_name, email, hashed_pwd.decode('utf-8')))
        conn.commit()
    except psycopg2.errors.UniqueViolation:
        conn.close()
        return jsonify({'message': 'Email already registered'}), 400
    except Exception as e:
        conn.close()
        return jsonify({'message': f'Error: {str(e)}'}), 500
    conn.close()
    
    return jsonify({'message': 'Account created successfully'}), 201

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    
    conn = database.get_db_connection()
    c = conn.cursor(cursor_factory=database.RealDictCursor)
    c.execute('SELECT * FROM users WHERE email = %s', (email,))
    user = c.fetchone()
    conn.close()
    
    if user and bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
        token = jwt.encode({
            'user_id': user['user_id'],
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        }, app.secret_key, algorithm="HS256")
        
        resp = jsonify({'message': 'Logged in successfully'})
        resp.set_cookie('token', token, httponly=True)
        return resp
        
    return jsonify({'message': 'Invalid credentials'}), 401

@app.route('/api/auth/logout', methods=['POST'])
def api_logout():
    resp = jsonify({'message': 'Logged out'})
    resp.set_cookie('token', '', expires=0)
    return resp

@app.route('/api/auth/google/login')
def google_login():
    redirect_uri = url_for('google_callback', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/api/auth/google/callback')
def google_callback():
    token = google.authorize_access_token()
    user_info = token.get('userinfo')
    
    if not user_info:
        return jsonify({'message': 'Failed to get user info from Google'}), 400

    email = user_info.get('email')
    full_name = user_info.get('name')
    
    conn = database.get_db_connection()
    c = conn.cursor(cursor_factory=database.RealDictCursor)
    c.execute('SELECT * FROM users WHERE email = %s', (email,))
    user = c.fetchone()
    
    # If user doesn't exist, create an account
    if not user:
        # Generate a random impossible password hash for Google-only users
        random_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for i in range(32))
        hashed_pwd = bcrypt.hashpw(random_password.encode('utf-8'), bcrypt.gensalt())
        
        c.execute('INSERT INTO users (full_name, email, password_hash) VALUES (%s, %s, %s) RETURNING user_id', 
                  (full_name, email, hashed_pwd.decode('utf-8')))
        user_id = c.fetchone()['user_id']
        conn.commit()
    else:
        user_id = user['user_id']
        
    conn.close()

    # Generate JWT Token
    jwt_token = jwt.encode({
        'user_id': user_id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }, app.secret_key, algorithm="HS256")
    
    # Set the cookie and redirect back to the dashboard
    resp = redirect(url_for('dashboard'))
    resp.set_cookie('token', jwt_token, httponly=True)
    return resp

# Main Engine Endpoints
@app.route('/api/generate-itinerary', methods=['POST'])
@token_required
def generate_itinerary():
    data = request.json
    destination = data.get("destination", "").strip()
    budget = float(data.get("budget", 0))
    # duration = int(data.get("duration", 1)) # Multi-day support can be added later
    # style = data.get("style", "moderate")

    print(f"Generating itinerary for {destination} with budget {budget}")
    # 1. Recommendation (Fetch Community Data)
    all_attractions = recommendation.get_top_attractions(destination)
    print(f"Found {len(all_attractions)} attractions.")
    
    if not all_attractions:
        return jsonify({'message': f'No community data found for "{destination}" yet. Try registering a past trip first!'}), 404

    # 2. MCTS (Select Attractions based on budget & rating)
    print("Selecting best attractions using MCTS...")
    selected = mcts_selector.select_best_attractions(all_attractions, budget)
    print(f"MCTS selected {len(selected)} attractions.")

    # 3. Fast TSP/LKH (Optimize Route)
    print("Optimizing route using 2-opt TSP...")
    optimized_route = optimizer.solve_tsp_2opt(selected)
    print("Route optimized.")

    # 4. Time Planner & Format
    print("Building final itinerary schedule...")
    final_plan = planner.build_itinerary(optimized_route)
    print("Finished building schedule.")
    
    # Enrich response with destination info
    final_plan['destination'] = destination
    final_plan['budget'] = budget

    return jsonify(final_plan)

@app.route('/api/experiences', methods=['POST'])
@token_required
def submit_experience():
    data = request.json
    token = request.cookies.get('token')
    user_data = jwt.decode(token, app.secret_key, algorithms=["HS256"])
    user_id = user_data['user_id']
    
    try:
        conn = database.get_db_connection()
        c = conn.cursor()
        
        # 1. Save the main trip experience row
        c.execute('''
            INSERT INTO trip_experiences (user_id, destination, trip_date, companion_type, stay_name, stay_price, stay_rating, total_expense)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING trip_id
        ''', (
            user_id, data.get('destination'), data.get('trip_date'), data.get('companion_type'), 
            data.get('stay_name'), data.get('stay_price', 0), data.get('stay_rating'), data.get('total_expense', 0)
        ))
        
        trip_id = c.fetchone()[0]
        
        # 2. Save each place visited
        places = data.get('places', [])
        for idx, place in enumerate(places):
            c.execute('''
                INSERT INTO places_visited (trip_id, place_order, place_name, place_rating, entry_fee, distance_from_prev, travel_method, travel_cost, travel_rating, experience_review)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                trip_id, idx, place.get('place_name'), place.get('place_rating'), place.get('entry_fee', 0),
                place.get('distance_from_prev'), place.get('travel_method'), place.get('travel_cost'), place.get('travel_rating'),
                place.get('experience_review')
            ))
            
        conn.commit()
        conn.close()
        return jsonify({'message': 'Trip Experience Logged Successfully!'}), 201
    except Exception as e:
        if 'conn' in locals() and conn:
            conn.close()
        print(f"Error saving experience: {str(e)}")
        return jsonify({'message': f'Error saving experience: {str(e)}'}), 500

@app.route('/api/my-trips', methods=['GET'])
@token_required
def get_my_trips():
    token = request.cookies.get('token')
    user_data = jwt.decode(token, app.secret_key, algorithms=["HS256"])
    user_id = user_data['user_id']
    
    conn = database.get_db_connection()
    c = conn.cursor(cursor_factory=database.RealDictCursor)
    
    # Fetch all trips for the user
    c.execute('SELECT * FROM trip_experiences WHERE user_id = %s ORDER BY trip_id DESC', (user_id,))
    trips = c.fetchall()
    
    results = []
    for trip in trips:
        trip_dict = dict(trip)
        # Fetch places for each trip
        c.execute('SELECT * FROM places_visited WHERE trip_id = %s ORDER BY place_order ASC', (trip['trip_id'],))
        places = c.fetchall()
        trip_dict['places'] = [dict(p) for p in places]
        results.append(trip_dict)
        
    conn.close()
    return jsonify(results)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
