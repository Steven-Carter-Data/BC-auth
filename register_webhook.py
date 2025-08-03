import requests
import os
from dotenv import load_dotenv

load_dotenv()

# Your Strava app credentials
CLIENT_ID = os.getenv('66224')
CLIENT_SECRET = os.getenv('f3e67948cf6ca5ba8f5733e722ff44fbe8e4137f')
CALLBACK_URL = 'https://jmyqtrpx1yxfwxptsyhu.supabase.co/functions/v1/strava-webhook'
VERIFY_TOKEN = '05978704df8c945ee89a3eca83453cc540595530'  # Choose a secure random string

def create_subscription():
    """Create a webhook subscription with Strava"""
    url = 'https://www.strava.com/api/v3/push_subscriptions'
    
    data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'callback_url': CALLBACK_URL,
        'verify_token': VERIFY_TOKEN
    }
    
    response = requests.post(url, data=data)
    
    if response.status_code == 201:
        print("Webhook subscription created successfully!")
        print("Subscription details:", response.json())
    else:
        print("Failed to create subscription:", response.status_code)
        print("Response:", response.text)

def list_subscriptions():
    """List existing webhook subscriptions"""
    url = 'https://www.strava.com/api/v3/push_subscriptions'
    params = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET
    }
    
    response = requests.get(url, params=params)
    print("Existing subscriptions:", response.json())

def delete_subscription(subscription_id):
    """Delete a webhook subscription"""
    url = f'https://www.strava.com/api/v3/push_subscriptions/{subscription_id}'
    params = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET
    }
    
    response = requests.delete(url, params=params)
    if response.status_code == 204:
        print(f"Subscription {subscription_id} deleted successfully!")
    else:
        print(f"Failed to delete subscription: {response.status_code}")

if __name__ == "__main__":
    print("1. List existing subscriptions")
    list_subscriptions()
    
    print("\n2. Creating new subscription...")
    create_subscription()
    
    print("\n3. List subscriptions after creation")
    list_subscriptions()