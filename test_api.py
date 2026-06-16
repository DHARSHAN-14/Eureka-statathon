import requests
import json

data = {
    'query': 'software developer',
    'top_k': 1,
    'search_mode': 'general'
}

resp = requests.post('http://localhost:5000/api/search', json=data, timeout=10)
result = resp.json()

# Print the structure of one result
if result.get('results'):
    print("First result structure:")
    print(json.dumps(result['results'][0], indent=2))
