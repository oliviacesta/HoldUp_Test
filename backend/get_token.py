# For now, we are generating test sessions locally using the Supabase API. 
# Later, we will need to test this with our actual mobile app and have users log in.

import os
import requests
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL").rstrip("/")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

# Replace with the test user email and password you created in your Supabase Dashboard
email = "oliviacesta@gmail.com"
password = "password"

url = f"{SUPABASE_URL}/auth/v1/token?grant_type=password"
headers = {
    "apikey": SUPABASE_ANON_KEY,
    "Content-Type": "application/json"
}
payload = {
    "email": email,
    "password": password
}

response = requests.post(url, json=payload, headers=headers)

if response.status_code == 200:
    data = response.json()
    print("\n--- YOUR JWT ACCESS TOKEN ---")
    print(data.get("access_token"))
    print("-------------------------------\n")
else:
    print("Failed to get token:", response.status_code, response.text)