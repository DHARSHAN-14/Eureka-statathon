import requests

try:
    res = requests.get("http://127.0.0.1:5000/")
    print("Status:", res.status_code)
    print("Content preview:", res.text[:200])
except Exception as e:
    print("Connection failed:", e)
