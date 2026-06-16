import requests
import json

API_URL = "http://127.0.0.1:5001/api/search"

queries = [
    # Exact/Partial Job Titles
    "Software Engineer",
    "Data Scientist",
    "Plumber",
    "Accountant",
    
    # Task descriptions / Action-oriented
    "designing bridges and roads",
    "treating sick animals",
    "fixing electrical wiring in houses",
    "teaching mathematics to high school students",
    
    # Broad/Generic terms
    "manager",
    "consultant",
    "technician",
    
    # Edge cases / Implicit meaning
    "code",
    "farm",
    "cook"
]

print("Running Accuracy Evaluation for FAISS-Only Search Model...\n")
print("-" * 80)

for query in queries:
    payload = {"query": query, "top_k": 3}
    try:
        response = requests.post(API_URL, json=payload)
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            print(f"Query: '{query}'")
            if not results:
                print("  No results found.")
            else:
                for i, r in enumerate(results):
                    title = r.get('occupation_title', 'Unknown')
                    score = r.get('final_score', 0.0)
                    sem_score = r.get('semantic_score', 0.0)
                    print(f"  {i+1}. [{score:.4f}] {title} (sem: {sem_score:.4f})")
            print("-" * 80)
        else:
            print(f"Error querying '{query}': HTTP {response.status_code}")
    except Exception as e:
        print(f"Failed to query '{query}': {e}")
