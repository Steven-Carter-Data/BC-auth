import requests
import os
import sys
from dotenv import load_dotenv

load_dotenv()

class StravaWebhookManager:
    def __init__(self):
        self.client_id = os.getenv('STRAVA_CLIENT_ID')
        self.client_secret = os.getenv('STRAVA_CLIENT_SECRET')
        self.callback_url = os.getenv('WEBHOOK_CALLBACK_URL')
        self.verify_token = os.getenv('STRAVA_WEBHOOK_VERIFY_TOKEN', 'bourbon_chasers_webhook_2024')
        
        # Validate required environment variables
        if not all([self.client_id, self.client_secret, self.callback_url]):
            print("❌ Missing required environment variables!")
            print("Required: STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, WEBHOOK_CALLBACK_URL")
            sys.exit(1)
    
    def create_subscription(self):
        """Create a webhook subscription with Strava"""
        print(f"🔄 Creating webhook subscription...")
        print(f"📡 Callback URL: {self.callback_url}")
        print(f"🔑 Verify Token: {self.verify_token}")
        
        url = "https://www.strava.com/api/v3/push_subscriptions"
        
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'callback_url': self.callback_url,
            'verify_token': self.verify_token
        }
        
        try:
            response = requests.post(url, data=data)
            
            if response.status_code == 201:
                subscription = response.json()
                print(f"✅ Webhook subscription created successfully!")
                print(f"📋 Subscription ID: {subscription['id']}")
                print(f"🎯 Callback URL: {subscription['callback_url']}")
                return subscription
            else:
                print(f"❌ Failed to create subscription")
                print(f"📊 Status Code: {response.status_code}")
                print(f"📝 Response: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Error creating subscription: {str(e)}")
            return None
    
    def list_subscriptions(self):
        """List all webhook subscriptions"""
        print("📋 Listing current webhook subscriptions...")
        
        url = "https://www.strava.com/api/v3/push_subscriptions"
        
        params = {
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }
        
        try:
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                subscriptions = response.json()
                print(f"📊 Found {len(subscriptions)} subscription(s):")
                
                if not subscriptions:
                    print("   (No subscriptions found)")
                else:
                    for i, sub in enumerate(subscriptions, 1):
                        print(f"   {i}. ID: {sub['id']}")
                        print(f"      📡 Callback: {sub['callback_url']}")
                        print(f"      📅 Created: {sub.get('created_at', 'Unknown')}")
                        print()
                
                return subscriptions
            else:
                print(f"❌ Failed to list subscriptions")
                print(f"📊 Status Code: {response.status_code}")
                print(f"📝 Response: {response.text}")
                return []
                
        except Exception as e:
            print(f"❌ Error listing subscriptions: {str(e)}")
            return []
    
    def delete_subscription(self, subscription_id):
        """Delete a webhook subscription"""
        print(f"🗑️  Deleting subscription ID: {subscription_id}")
        
        url = f"https://www.strava.com/api/v3/push_subscriptions/{subscription_id}"
        
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }
        
        try:
            response = requests.delete(url, data=data)
            
            if response.status_code == 204:
                print(f"✅ Subscription {subscription_id} deleted successfully!")
                return True
            else:
                print(f"❌ Failed to delete subscription")
                print(f"📊 Status Code: {response.status_code}")
                print(f"📝 Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error deleting subscription: {str(e)}")
            return False
    
    def test_webhook_endpoint(self):
        """Test if the webhook endpoint is accessible"""
        print(f"🧪 Testing webhook endpoint: {self.callback_url}")
        
        try:
            # Test the health check endpoint
            health_url = self.callback_url.replace('/webhook', '/')
            response = requests.get(health_url, timeout=10)
            
            if response.status_code == 200:
                print("✅ Webhook endpoint is accessible!")
                print(f"📝 Response: {response.text}")
                return True
            else:
                print(f"⚠️  Webhook endpoint returned status: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Cannot reach webhook endpoint: {str(e)}")
            print("💡 Make sure your webhook server is running and accessible via HTTPS")
            return False

def main():
    print("🏃‍♂️ Bourbon Chasers Strava Webhook Manager")
    print("=" * 50)
    
    manager = StravaWebhookManager()
    
    while True:
        print("\nWhat would you like to do?")
        print("1. 📋 List current subscriptions")
        print("2. ➕ Create new subscription")
        print("3. 🗑️  Delete a subscription")
        print("4. 🧪 Test webhook endpoint")
        print("5. 🚪 Exit")
        
        choice = input("\nEnter your choice (1-5): ").strip()
        
        if choice == '1':
            print()
            manager.list_subscriptions()
            
        elif choice == '2':
            print()
            if manager.test_webhook_endpoint():
                print()
                manager.create_subscription()
            else:
                print("❌ Cannot create subscription - webhook endpoint is not accessible")
                
        elif choice == '3':
            print()
            subscriptions = manager.list_subscriptions()
            if subscriptions:
                try:
                    sub_id = input("\nEnter subscription ID to delete: ").strip()
                    if sub_id:
                        manager.delete_subscription(int(sub_id))
                except ValueError:
                    print("❌ Invalid subscription ID")
            else:
                print("No subscriptions to delete")
                
        elif choice == '4':
            print()
            manager.test_webhook_endpoint()
            
        elif choice == '5':
            print("👋 Goodbye!")
            break
            
        else:
            print("❌ Invalid choice. Please try again.")

if __name__ == "__main__":
    main()