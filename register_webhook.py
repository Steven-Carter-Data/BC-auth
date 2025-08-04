import requests
import os
from dotenv import load_dotenv

load_dotenv()

# Your Strava app credentials
CLIENT_ID = os.getenv('STRAVA_CLIENT_ID')
CLIENT_SECRET = os.getenv('STRAVA_CLIENT_SECRET')
# Fixed the project ID - was jmyqtrpx1yxfwxptsyhu, should be jmyqirpxiyxfwxpisyhu
CALLBACK_URL = 'https://jmyqirpxiyxfwxpisyhu.supabase.co/functions/v1/strava-webhook'
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
    
    print(f"Creating subscription with callback URL: {CALLBACK_URL}")
    response = requests.post(url, data=data)
    
    if response.status_code == 201:
        print("Webhook subscription created successfully!")
        print("Subscription details:", response.json())
    else:
        print("Failed to create subscription:", response.status_code)
        print("Response:", response.text)
        
        # If we get a conflict error, it might be because a subscription already exists
        if response.status_code == 409:
            print("A subscription may already exist. Check existing subscriptions.")

def list_subscriptions():
    """List existing webhook subscriptions"""
    url = 'https://www.strava.com/api/v3/push_subscriptions'
    params = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET
    }
    
    response = requests.get(url, params=params)
    print("Existing subscriptions:", response.json())
    return response.json()

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
        print(f"Response: {response.text}")

def test_webhook_endpoint():
    """Test if the webhook endpoint is accessible"""
    print(f"Testing webhook endpoint: {CALLBACK_URL}")
    try:
        response = requests.get(CALLBACK_URL, timeout=10)
        print(f"Endpoint response: {response.status_code}")
        print(f"Response body: {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error testing endpoint: {e}")
        return False

if __name__ == "__main__":
    print("=== Strava Webhook Registration ===")
    print(f"Using Client ID: {CLIENT_ID}")
    print(f"Using Client Secret: {CLIENT_SECRET[:10]}..." if CLIENT_SECRET else "Client Secret: None")
    print(f"Using Verify Token: {VERIFY_TOKEN}")
    print(f"Using Callback URL: {CALLBACK_URL}")
    print()
    
    print("1. Testing webhook endpoint...")
    if test_webhook_endpoint():
        print("✅ Webhook endpoint is accessible")
    else:
        print("❌ Webhook endpoint is not accessible - this will cause registration to fail")
    print()
    
    print("2. Listing existing subscriptions...")
    existing_subs = list_subscriptions()
    print()
    
    # Delete existing subscriptions if any
    if existing_subs and len(existing_subs) > 0:
        print("3. Found existing subscriptions. Deleting them first...")
        for sub in existing_subs:
            if 'id' in sub:
                delete_subscription(sub['id'])
        print()
    
    print("4. Creating new subscription...")
    create_subscription()
    print()
    
    print("5. Listing subscriptions after creation...")
    list_subscriptions()