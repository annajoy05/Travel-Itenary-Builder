import requests
import jwt
import datetime

# Create a mock token
token = jwt.encode({
    'user_id': 1, # assuming user 1 exists or testing doesn't strictly check db existence in the route
    'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)
}, 'super_secret_temporary_key', algorithm="HS256")

# Ping the server
cookies = {'token': token}
response = requests.post(
    'http://127.0.0.1:5000/api/generate-itinerary',
    json={'destination': 'Munnar', 'budget': 5000},
    cookies=cookies
)

print(response.status_code)
print(response.json())
