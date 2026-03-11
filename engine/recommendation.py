import os
import sys

# Add parent directory to path to import database
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import database

def get_db_connection():
    return database.get_db_connection()

def get_top_attractions(destination, limit=20):
    """
    Aggregates community data to find top attractions for a destination.
    Returns a list of dicts with name, avg_rating, avg_fee, and popularity count.
    """
    conn = get_db_connection()
    c = conn.cursor(cursor_factory=database.RealDictCursor)
    
    query = '''
        SELECT 
            p.place_name,
            COALESCE(AVG(p.place_rating), 3.0) as avg_rating,
            COALESCE(AVG(p.entry_fee), 0.0) as avg_fee,
            COUNT(p.place_id) as visitation_count
        FROM places_visited p
        JOIN trip_experiences t ON p.trip_id = t.trip_id
        WHERE LOWER(t.destination) = LOWER(%s)
        GROUP BY p.place_name
        ORDER BY avg_rating DESC, visitation_count DESC
        LIMIT %s
    '''
    
    c.execute(query, (destination, limit))
    rows = c.fetchall()
    
    results = []
    for row in rows:
        d = dict(row)
        # Fetch up to 3 recent reviews for this place
        reviews_query = "SELECT experience_review FROM places_visited WHERE place_name = %s AND experience_review IS NOT NULL AND experience_review != '' ORDER BY place_id DESC LIMIT 3"
        c.execute(reviews_query, (d['place_name'],))
        reviews = c.fetchall()
        d['reviews'] = [r['experience_review'] for r in reviews]
        results.append(d)
        
    conn.close()
    return results

def get_travel_stats(destination):
    """
    Calculates average travel costs and ratings between places for a destination.
    """
    conn = get_db_connection()
    c = conn.cursor(cursor_factory=database.RealDictCursor)
    
    query = '''
        SELECT 
            travel_method,
            AVG(travel_cost) as avg_cost,
            AVG(travel_rating) as avg_rating,
            AVG(distance_from_prev) as avg_distance,
            COUNT(*) as frequency
        FROM places_visited p
        JOIN trip_experiences t ON p.trip_id = t.trip_id
        WHERE LOWER(t.destination) = LOWER(%s) AND travel_method IS NOT NULL
        GROUP BY travel_method
    '''
    
    c.execute(query, (destination,))
    rows = c.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

if __name__ == '__main__':
    # Test with mock data if needed
    stats = get_top_attractions('Munnar')
    print("Top Attractions in Munnar:")
    for s in stats:
        print(f"- {s['place_name']}: {s['avg_rating']} stars (Fee: ₹{s['avg_fee']})")
