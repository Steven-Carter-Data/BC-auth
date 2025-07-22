import time
import streamlit as st
from database import Database
from strava_client import StravaClient

def handle_authentication():
    """Handle Strava OAuth flow"""
    strava = StravaClient()
    db = Database()
    
    # Check for authorization code in URL
    query_params = st.query_params
    
    if 'code' in query_params:
        # Exchange code for token
        code = query_params['code']
        
        try:
            token_response = strava.exchange_code_for_token(code)
            
            # Get the authenticated athlete with both tokens set
            strava.set_access_token(token_response['access_token'], token_response['refresh_token'])
            athlete = strava.get_athlete()
            
            # Save athlete to database
            athlete_data = {
                'id': athlete.id,
                'username': athlete.username if athlete.username else f"athlete_{athlete.id}",
                'firstname': athlete.firstname,
                'lastname': athlete.lastname,
                'access_token': token_response['access_token'],
                'refresh_token': token_response['refresh_token'],
                'expires_at': token_response['expires_at']
            }
            
            db.upsert_athlete(athlete_data)
            
            # Store in session
            st.session_state['athlete_id'] = athlete_data['id']
            st.session_state['access_token'] = athlete_data['access_token']
            st.session_state['expires_at'] = athlete_data['expires_at']
            
            # Clear URL parameters
            st.query_params.clear()
            
            st.success(f"Successfully authenticated as {athlete_data['firstname']} {athlete_data['lastname']}!")
            st.rerun()
            
        except Exception as e:
            st.error(f"Authentication failed: {str(e)}")
            st.write("Debug - Full error:", e)
    
    return strava.get_authorization_url()

def refresh_token_if_needed(athlete_id):
    """Refresh token if expired"""
    db = Database()
    athlete = db.get_athlete(athlete_id).data
    
    if athlete and time.time() > athlete['expires_at'] - 300:  # 5 min buffer
        strava = StravaClient()
        token_response = strava.refresh_access_token(athlete['refresh_token'])
        
        # Update database with complete athlete data (preserve existing fields)
        updated_athlete_data = {
            'id': athlete_id,
            'username': athlete['username'],  # Preserve existing username
            'firstname': athlete['firstname'],  # Preserve existing firstname
            'lastname': athlete['lastname'],    # Preserve existing lastname
            'access_token': token_response['access_token'],
            'refresh_token': token_response['refresh_token'],
            'expires_at': token_response['expires_at']
        }
        
        db.upsert_athlete(updated_athlete_data)
        
        return token_response['access_token']
    
    return athlete['access_token']