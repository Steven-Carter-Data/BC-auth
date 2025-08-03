import os
import time
from stravalib.client import Client
from dotenv import load_dotenv
import streamlit as st

load_dotenv()

class StravaClient:
    def __init__(self):
        self.client = Client()
        
        # Try to get from Streamlit secrets first, then from environment
        try:
            self.client_id = st.secrets["STRAVA_CLIENT_ID"]
            self.client_secret = st.secrets["STRAVA_CLIENT_SECRET"]
            self.redirect_uri = st.secrets["REDIRECT_URI"]
        except (KeyError, AttributeError, FileNotFoundError):
            self.client_id = os.getenv('STRAVA_CLIENT_ID')
            self.client_secret = os.getenv('STRAVA_CLIENT_SECRET')
            self.redirect_uri = os.getenv('REDIRECT_URI', 'http://localhost:8501')
        
    def get_authorization_url(self):
        """Get OAuth authorization URL"""
        return self.client.authorization_url(
            client_id=self.client_id,
            redirect_uri=self.redirect_uri,
            scope=['activity:read_all', 'profile:read_all', 'read_all'],
            approval_prompt='auto'  # Don't force re-approval every time
        )
    
    def exchange_code_for_token(self, code):
        """Exchange authorization code for access token"""
        token_response = self.client.exchange_code_for_token(
            client_id=self.client_id,
            client_secret=self.client_secret,
            code=code
        )
        return token_response
    
    def refresh_access_token(self, refresh_token):
        """Refresh expired access token"""
        return self.client.refresh_access_token(
            client_id=self.client_id,
            client_secret=self.client_secret,
            refresh_token=refresh_token
        )
    
    def set_access_token(self, access_token, refresh_token=None):
        """Set access token and refresh token for API calls"""
        self.client.access_token = access_token
        if refresh_token:
            self.client.refresh_token = refresh_token
    
    def get_athlete(self):
        """Get authenticated athlete"""
        return self.client.get_athlete()
    
    def get_activities(self, after=None, limit=50):
        """Get athlete activities"""
        return self.client.get_activities(after=after, limit=limit)
    
    def get_activity_by_id(self, activity_id):
        """Get detailed activity data"""
        return self.client.get_activity(activity_id)
    
    def get_activity_zones(self, activity_id):
        """Get heart rate zones for an activity"""
        try:
            zones = self.client.get_activity_zones(activity_id)
            
            # Extract heart rate zones
            for zone in zones:
                if zone.type == 'heartrate':
                    return {
                        'zone_1_time': zone.distribution_buckets[0].time if len(zone.distribution_buckets) > 0 else 0,
                        'zone_2_time': zone.distribution_buckets[1].time if len(zone.distribution_buckets) > 1 else 0,
                        'zone_3_time': zone.distribution_buckets[2].time if len(zone.distribution_buckets) > 2 else 0,
                        'zone_4_time': zone.distribution_buckets[3].time if len(zone.distribution_buckets) > 3 else 0,
                        'zone_5_time': zone.distribution_buckets[4].time if len(zone.distribution_buckets) > 4 else 0,
                    }
        except Exception as e:
            print(f"Error fetching heart rate zones: {e}")
        
        return None