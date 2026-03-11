from datetime import datetime, timedelta

def build_itinerary(route: list, start_time: str = "09:00", stay_per_place: int = 120) -> dict:
    """
    Transforms an optimized route into a timed itinerary with estimated costs.
    Handles a single-day itinerary for now.
    """
    if not route:
        return {"days": [], "total_cost": 0.0}

    itinerary = []
    # Start at 09:00 AM
    current_time = datetime.strptime(start_time, "%H:%M")
    total_cost = 0.0
    
    for i, place in enumerate(route):
        # 1. Travel Time Simulation
        if i > 0:
            # Assumption: ~30 minutes travel between nearby attractions 
            current_time += timedelta(minutes=30)
            # Add a small travel cost (avg 100 per hop)
            total_cost += 100.0
            
        # 2. Place Visit Entry
        visit_entry = {
            "time": current_time.strftime("%H:%M"),
            "place": place.get('place_name', 'Unknown'),
            "cost": float(place.get('avg_fee', 0.0)),
            "rating": round(float(place.get('avg_rating', 0.0)), 1),
            "reviews": place.get('reviews', [])
        }
        itinerary.append(visit_entry)
        total_cost += float(place.get('avg_fee', 0.0))
        
        # 3. Time Spent at Attraction
        current_time += timedelta(minutes=stay_per_place)
        
    return {
        "days": [
            {
                "day_number": 1,
                "route": itinerary
            }
        ],
        "total_cost": round(total_cost, 2)
    }

if __name__ == '__main__':
    # Test stub
    mock_route = [
        {'place_name': 'Tea Museum', 'avg_fee': 200, 'avg_rating': 4.5},
        {'place_name': 'Mattupetty Dam', 'avg_fee': 50, 'avg_rating': 4.2}
    ]
    plan = build_itinerary(mock_route)
    print("Generated Plan:")
    for item in plan['days'][0]['route']:
        print(f"{item['time']} - {item['place']} (₹{item['cost']})")
    print(f"Total Cost: ₹{plan['total_cost']}")
