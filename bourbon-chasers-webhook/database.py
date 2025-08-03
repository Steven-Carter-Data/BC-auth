import os
import streamlit as st
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

class Database:
    def __init__(self):
        # Try to get from Streamlit secrets first, then from environment
        try:
            url = st.secrets["SUPABASE_URL"]
            key = st.secrets["SUPABASE_KEY"]
        except (KeyError, AttributeError, FileNotFoundError):
            url = os.getenv("SUPABASE_URL")
            key = os.getenv("SUPABASE_KEY")
            
        if not url or not key:
            raise ValueError("Supabase URL and key must be provided")
            
        self.supabase: Client = create_client(url, key)
    
    def upsert_athlete(self, athlete_data):
        """Insert or update athlete"""
        return self.supabase.table('athletes').upsert(athlete_data).execute()
    
    def get_athlete(self, athlete_id):
        """Get athlete by ID"""
        return self.supabase.table('athletes').select("*").eq('id', athlete_id).single().execute()
    
    def get_all_athletes(self):
        """Get all athletes"""
        return self.supabase.table('athletes').select("*").order('firstname').execute()
    
    def upsert_activity(self, activity_data):
        """Insert or update activity"""
        return self.supabase.table('activities').upsert(activity_data).execute()
    
    def get_activities(self, athlete_id, limit=100):
        """Get activities for an athlete"""
        return self.supabase.table('activities').select("*").eq('athlete_id', athlete_id).order('start_date', desc=True).limit(limit).execute()
    
    def upsert_heart_rate_zones(self, zone_data):
        """Insert or update heart rate zones"""
        return self.supabase.table('heart_rate_zones').upsert(zone_data).execute()
    
    def get_latest_activity_date(self, athlete_id):
        """Get the most recent activity date for an athlete"""
        result = self.supabase.table('activities').select('start_date').eq('athlete_id', athlete_id).order('start_date', desc=True).limit(1).execute()
        if result.data:
            return result.data[0]['start_date']
        return None