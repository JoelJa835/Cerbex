#requests_example.py
import requests
import json
import math

def main():
    response = requests.get(
        "https://httpbin.org/anything", 
        params={"msg": "hello", "n": 42}
    )
    print("Status code:", response.status_code)

    data = json.loads(response.text)
    print("Parsed JSON data:", data)

if __name__ == "__main__":
    main()
