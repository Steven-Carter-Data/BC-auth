import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

class Database:
    def __init__(self):
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        self.supabase: Client = create_client(url, key)
    
    def upsert_athlete(self, athlete_data):
        """Insert or update athlete"""
        return self.supabase.table('athletes').upsert(athlete_data).execute()
    
    def get_athlete(self, athlete_id):
        """Get athlete by ID"""
        return self.supabase.table('athletes').select("*").eq('id', athlete_id).single().execute()
    
    def get_all_athletes(self):
        """Get all athletes"""
        return self.supabase.table('athletes').select("*").execute()
    
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