import os
import sys

# Add parent directory to path to import database
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import database

def get_distance_matrix(attractions):
    """
    Creates a distance matrix for the selected attractions based on community data.
    If no data exists for a pair, it uses a default distance (e.g. 10km).
    """
    names = [a['place_name'] for a in attractions]
    n = len(names)
    matrix = [[10.0 for _ in range(n)] for _ in range(n)]
    for i in range(n):
        matrix[i][i] = 0.0

    conn = database.get_db_connection()
    c = conn.cursor()
    
    for i in range(n):
        for j in range(n):
            if i == j: continue
            
            # Find any trip where i and j are adjacent
            q = '''
                SELECT AVG(p2.distance_from_prev), AVG(p2.travel_rating)
                FROM places_visited p1
                JOIN places_visited p2 ON p1.trip_id = p2.trip_id 
                WHERE (p1.place_name = %s AND p2.place_name = %s AND p2.place_order = p1.place_order + 1)
                   OR (p1.place_name = %s AND p2.place_name = %s AND p1.place_order = p2.place_order + 1)
            '''
            c.execute(q, (names[i], names[j], names[j], names[i]))
            res = c.fetchone()
            if res and res[0]:
                dist = res[0]
                rating = res[1] if res[1] else 3.0 # Default rating
                # "Cost" for TSP: lower is better. 
                # We divide distance by rating to prioritize higher-rated (better) paths.
                # A 5-star 10km path is better than a 2-star 10km path.
                matrix[i][j] = dist / (rating / 3.0) 
                
    conn.close()
    return matrix

def solve_tsp_2opt(attractions: list) -> list:
    """
    Solves the TSP for the given attractions using the 2-opt heuristic.
    """
    n = len(attractions)
    if n <= 2:
        return list(attractions)

    matrix = get_distance_matrix(attractions)
    
    # Initial tour: as provided
    tour = list(range(n))
    
    def get_tour_distance(t: list) -> float:
        dist = 0.0
        for i in range(len(t) - 1):
            dist += matrix[t[i]][t[i+1]]
        return dist

    best_distance = get_tour_distance(tour)
    improved = True
    
    # Limit iterations for 2-opt
    max_iters = 50
    iters = 0
    
    while improved and iters < max_iters:
        improved = False
        iters += 1
        for i in range(n):
            for j in range(i + 2, n):
                # Reverse the segment between i+1 and j
                new_tour = tour[:i+1] + tour[i+1:j+1][::-1] + tour[j+1:]
                new_dist = get_tour_distance(new_tour)
                if new_dist < best_distance:
                    best_distance = new_dist
                    tour = new_tour
                    improved = True
    
    return [attractions[idx] for idx in tour]

if __name__ == '__main__':
    # Test stub
    mock_attr = [
        {'place_name': 'A'},
        {'place_name': 'B'},
        {'place_name': 'C'},
        {'place_name': 'D'},
    ]
    # Assuming A-B=1, B-C=1, C-D=1, A-D=10, etc.
    final_route = solve_tsp_2opt(mock_attr)
    print("Optimized Route Order:")
    for a in final_route:
        print(f"- {a['place_name']}")
