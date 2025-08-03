from flask import Flask, request, jsonify
import os
import sys
import time
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import your existing modules
from database import Database
from strava_client import StravaClient
from auth import refresh_token_if_needed

app = Flask(__name__)

# Webhook verification token - set this in your environment variables
WEBHOOK_VERIFY_TOKEN = os.getenv('STRAVA_WEBHOOK_VERIFY_TOKEN', 'bourbon_chasers_webhook_2024')

@app.route('/', methods=['GET'])
def health_check():
    """Simple health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'Bourbon Chasers Strava Webhook',
        'timestamp': time.time()
    })

@app.route('/webhook', methods=['GET', 'POST'])
def strava_webhook():
    """Handle Strava webhook events"""
    
    if request.method == 'GET':
        # Webhook subscription verification
        challenge = request.args.get('hub.challenge')
        verify_token = request.args.get('hub.verify_token')
        
        logger.info(f"Webhook verification request received. Token: {verify_token}")
        
        if verify_token == WEBHOOK_VERIFY_TOKEN:
            logger.info("Webhook verification successful")
            return jsonify({'hub.challenge': challenge})
        else:
            logger.error("Webhook verification failed - invalid token")
            return 'Forbidden', 403
    
    elif request.method == 'POST':
        # Process webhook event
        try:
            event_data = request.get_json()
            logger.info(f"Received webhook event: {event_data}")
            
            # Only process activity creation events
            if (event_data.get('object_type') == 'activity' and 
                event_data.get('aspect_type') == 'create'):
                
                athlete_id = event_data.get('owner_id')
                activity_id = event_data.get('object_id')
                
                logger.info(f"Processing new activity {activity_id} for athlete {athlete_id}")
                
                # Sync the new activity
                success = sync_single_activity(athlete_id, activity_id)
                
                if success:
                    logger.info(f"Successfully processed activity {activity_id}")
                else:
                    logger.warning(f"Failed to process activity {activity_id}")
            
            else:
                logger.info(f"Ignoring event: {event_data.get('object_type')} - {event_data.get('aspect_type')}")
        
        except Exception as e:
            logger.error(f"Error processing webhook: {str(e)}")
        
        # Always return 200 OK to acknowledge receipt
        return 'OK', 200

def sync_single_activity(athlete_id, activity_id):
    """Sync a single activity for an athlete"""
    try:
        db = Database()
        strava = StravaClient()
        
        # Check if athlete exists in our database
        try:
            athlete_result = db.get_athlete(athlete_id)
            if not athlete_result.data:
                logger.warning(f"Athlete {athlete_id} not found in database, skipping")
                return False
        except Exception as e:
            logger.warning(f"Athlete {athlete_id} not found in database: {str(e)}")
            return False
        
        # Get fresh access token
        access_token = refresh_token_if_needed(athlete_id)
        athlete_data = athlete_result.data
        strava.set_access_token(access_token, athlete_data['refresh_token'])
        
        # Get detailed activity data
        detailed_activity = strava.get_activity_by_id(activity_id)
        
        # Helper function to extract seconds from Duration objects
        def get_total_seconds(duration_obj):
            if duration_obj is None:
                return 0
            if hasattr(duration_obj, 'total_seconds'):
                return int(duration_obj.total_seconds())
            elif isinstance(duration_obj, (int, float)):
                return int(duration_obj)
            elif hasattr(duration_obj, 'seconds'):
                return int(duration_obj.total_seconds())
            else:
                return 0
        
        # Prepare activity data (same as your existing sync function)
        activity_data = {
            'id': detailed_activity.id,
            'athlete_id': athlete_id,
            'name': detailed_activity.name,
            'sport_type': str(detailed_activity.sport_type),
            'start_date': detailed_activity.start_date_local.isoformat(),
            'distance': float(detailed_activity.distance),
            'moving_time': get_total_seconds(detailed_activity.moving_time),
            'elapsed_time': get_total_seconds(detailed_activity.elapsed_time),
            'total_elevation_gain': float(detailed_activity.total_elevation_gain) if detailed_activity.total_elevation_gain else 0,
            'average_heartrate': detailed_activity.average_heartrate if hasattr(detailed_activity, 'average_heartrate') else None,
            'max_heartrate': detailed_activity.max_heartrate if hasattr(detailed_activity, 'max_heartrate') else None,
            'average_speed': float(detailed_activity.average_speed) if detailed_activity.average_speed else 0,
            'max_speed': float(detailed_activity.max_speed) if detailed_activity.max_speed else 0,
            'average_watts': detailed_activity.average_watts if hasattr(detailed_activity, 'average_watts') else None,
            'kilojoules': detailed_activity.kilojoules if hasattr(detailed_activity, 'kilojoules') else None,
            'description': detailed_activity.description if detailed_activity.description else None
        }
        
        # Save activity
        db.upsert_activity(activity_data)
        logger.info(f"Saved activity {activity_id} to database")
        
        # Get heart rate zones if available
        if hasattr(detailed_activity, 'has_heartrate') and detailed_activity.has_heartrate:
            try:
                zones = strava.get_activity_zones(activity_id)
                if zones:
                    zones['activity_id'] = activity_id
                    db.upsert_heart_rate_zones(zones)
                    logger.info(f"Saved heart rate zones for activity {activity_id}")
            except Exception as e:
                logger.warning(f"Could not fetch heart rate zones for activity {activity_id}: {str(e)}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error syncing activity {activity_id} for athlete {athlete_id}: {str(e)}")
        return False

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)