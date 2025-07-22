import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time

from database import Database
from strava_client import StravaClient
from auth import handle_authentication, refresh_token_if_needed

# Page config
st.set_page_config(
    page_title="Bourbon Chasers Strava Tracker",
    page_icon="🏃‍♂️",
    layout="wide"
)

# Initialize session state
if 'athlete_id' not in st.session_state:
    st.session_state['athlete_id'] = None

def sync_activities(athlete_id, progress_bar):
    """Sync activities for an athlete"""
    db = Database()
    strava = StravaClient()
    
    # Get fresh access token and athlete data
    access_token = refresh_token_if_needed(athlete_id)
    athlete_data = db.get_athlete(athlete_id).data
    strava.set_access_token(access_token, athlete_data['refresh_token'])
    
    # Get latest activity date from database
    latest_date = db.get_latest_activity_date(athlete_id)
    after = datetime.fromisoformat(latest_date) if latest_date else None
    
    # Fetch activities
    activities = list(strava.get_activities(after=after, limit=100))
    total_activities = len(activities)
    
    if total_activities == 0:
        st.info("No new activities to sync")
        return
    
    st.info(f"Found {total_activities} new activities to sync")
    
    # Process each activity
    for idx, activity in enumerate(activities):
        progress_bar.progress((idx + 1) / total_activities)
        
        # Get detailed activity data
        detailed_activity = strava.get_activity_by_id(activity.id)
        
        # Helper function to extract seconds from Duration objects
        def get_total_seconds(duration_obj):
            if duration_obj is None:
                return 0
            # Duration objects have total_seconds() method
            if hasattr(duration_obj, 'total_seconds'):
                return int(duration_obj.total_seconds())
            # Fallback: if it's already an integer
            elif isinstance(duration_obj, (int, float)):
                return int(duration_obj)
            # If it has seconds attribute (timedelta)
            elif hasattr(duration_obj, 'seconds'):
                return int(duration_obj.total_seconds())
            else:
                return 0
        
        # Prepare activity data
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
        
        # Get heart rate zones if available
        if hasattr(detailed_activity, 'has_heartrate') and detailed_activity.has_heartrate:
            try:
                zones = strava.get_activity_zones(activity.id)
                if zones:
                    zones['activity_id'] = activity.id
                    db.upsert_heart_rate_zones(zones)
            except Exception as e:
                st.warning(f"Could not fetch heart rate zones for activity {activity.id}: {str(e)}")
        
        # Rate limit management - pause between every activity and longer every 10
        if (idx + 1) % 10 == 0:
            time.sleep(5)  # Longer pause every 10 activities
        else:
            time.sleep(1)  # Short pause between each activity
    
    st.success(f"Successfully synced {total_activities} activities!")

def main():
    st.title("🏃‍♂️ Bourbon Chasers Strava Tracker")
    
    db = Database()
    
    # Sidebar for authentication and athlete selection
    with st.sidebar:
        st.header("Authentication")
        
        if st.session_state['athlete_id']:
            athlete = db.get_athlete(st.session_state['athlete_id']).data
            st.success(f"Logged in as: {athlete['firstname']} {athlete['lastname']}")
            
            if st.button("Logout"):
                st.session_state['athlete_id'] = None
                st.rerun()
        else:
            auth_url = handle_authentication()
            st.markdown(f"[Connect with Strava]({auth_url})")
        
        st.divider()
        
        # Show all authenticated athletes
        st.header("Bourbon Chasers Members")
        athletes = db.get_all_athletes().data
        
        if athletes:
            for athlete in athletes:
                if st.button(f"👤 {athlete['firstname']} {athlete['lastname']}", key=f"athlete_{athlete['id']}"):
                    st.session_state['athlete_id'] = athlete['id']
                    st.rerun()
        else:
            st.info("No athletes connected yet")
    
    # Main content area
    if st.session_state['athlete_id']:
        athlete_id = st.session_state['athlete_id']
        athlete = db.get_athlete(athlete_id).data
        
        st.header(f"Dashboard for {athlete['firstname']} {athlete['lastname']}")
        
        # Sync button
        col1, col2, col3 = st.columns([1, 1, 3])
        with col1:
            if st.button("🔄 Sync Activities", type="primary"):
                progress_bar = st.progress(0)
                sync_activities(athlete_id, progress_bar)
                st.rerun()
        
        # Get activities
        activities_result = db.get_activities(athlete_id, limit=100)
        
        if activities_result.data:
            activities_df = pd.DataFrame(activities_result.data)
            
            # Convert data types
            activities_df['start_date'] = pd.to_datetime(activities_df['start_date'])
            activities_df['distance_km'] = activities_df['distance'] / 1000
            activities_df['moving_time_hours'] = activities_df['moving_time'] / 3600
            activities_df['average_speed_kmh'] = activities_df['average_speed'] * 3.6
            
            # Display metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                total_distance = activities_df['distance_km'].sum()
                st.metric("Total Distance", f"{total_distance:,.0f} km")
            
            with col2:
                total_time = activities_df['moving_time_hours'].sum()
                st.metric("Total Time", f"{total_time:,.0f} hours")
            
            with col3:
                total_activities = len(activities_df)
                st.metric("Total Activities", total_activities)
            
            with col4:
                avg_hr = activities_df['average_heartrate'].mean()
                if pd.notna(avg_hr):
                    st.metric("Avg Heart Rate", f"{avg_hr:.0f} bpm")
                else:
                    st.metric("Avg Heart Rate", "N/A")
            
            # Tabs for different views
            tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview", "❤️ Heart Rate Zones", "📈 Trends", "📋 Activities List"])
            
            with tab1:
                # Activity type distribution
                col1, col2 = st.columns(2)
                
                with col1:
                    activity_counts = activities_df['sport_type'].value_counts()
                    fig = px.pie(values=activity_counts.values, names=activity_counts.index, 
                                title="Activity Types Distribution")
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    # Distance by activity type
                    distance_by_type = activities_df.groupby('sport_type')['distance_km'].sum().sort_values(ascending=True)
                    fig = px.bar(x=distance_by_type.values, y=distance_by_type.index, 
                                orientation='h', title="Distance by Activity Type")
                    fig.update_layout(xaxis_title="Distance (km)", yaxis_title="Activity Type")
                    st.plotly_chart(fig, use_container_width=True)
                
                # Weekly activity pattern
                activities_df['weekday'] = activities_df['start_date'].dt.day_name()
                activities_df['hour'] = activities_df['start_date'].dt.hour
                
                weekday_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                heatmap_data = activities_df.groupby(['weekday', 'hour']).size().reset_index(name='count')
                heatmap_pivot = heatmap_data.pivot(index='weekday', columns='hour', values='count').fillna(0)
                heatmap_pivot = heatmap_pivot.reindex(weekday_order)
                
                fig = px.imshow(heatmap_pivot, 
                              labels=dict(x="Hour of Day", y="Day of Week", color="Activities"),
                              title="Activity Heatmap by Day and Hour",
                              color_continuous_scale="Blues")
                st.plotly_chart(fig, use_container_width=True)
            
            with tab2:
                # Heart Rate Zone Analysis
                st.subheader("Heart Rate Zone Distribution")
                
                # Get heart rate zone data using a proper join query
                try:
                    hr_zones_result = db.supabase.table('heart_rate_zones').select(
                        """
                        *,
                        activities!inner(
                            name,
                            sport_type,
                            start_date,
                            athlete_id
                        )
                        """
                    ).eq('activities.athlete_id', athlete_id).limit(50).execute()
                    
                    if hr_zones_result.data:
                        # Flatten the data structure
                        hr_zones_data = []
                        for zone_record in hr_zones_result.data:
                            activity_data = zone_record['activities']
                            hr_zones_data.append({
                                'name': activity_data['name'],
                                'sport_type': activity_data['sport_type'],
                                'start_date': activity_data['start_date'],
                                'zone_1_time': zone_record.get('zone_1_time', 0),
                                'zone_2_time': zone_record.get('zone_2_time', 0),
                                'zone_3_time': zone_record.get('zone_3_time', 0),
                                'zone_4_time': zone_record.get('zone_4_time', 0),
                                'zone_5_time': zone_record.get('zone_5_time', 0),
                            })
                        
                        hr_zones_df = pd.DataFrame(hr_zones_data)
                        
                        # Sort by start_date after creating the dataframe
                        hr_zones_df['start_date'] = pd.to_datetime(hr_zones_df['start_date'])
                        hr_zones_df = hr_zones_df.sort_values('start_date', ascending=False)
                        
                        # Calculate total time in each zone
                        zone_totals = {
                            'Zone 1 (Recovery)': hr_zones_df['zone_1_time'].sum() / 3600,
                            'Zone 2 (Endurance)': hr_zones_df['zone_2_time'].sum() / 3600,
                            'Zone 3 (Tempo)': hr_zones_df['zone_3_time'].sum() / 3600,
                            'Zone 4 (Threshold)': hr_zones_df['zone_4_time'].sum() / 3600,
                            'Zone 5 (VO2 Max)': hr_zones_df['zone_5_time'].sum() / 3600
                        }
                        
                        # Zone distribution pie chart
                        fig = px.pie(values=list(zone_totals.values()), names=list(zone_totals.keys()),
                                    title="Total Time in Each Heart Rate Zone (hours)")
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # Zone distribution over time
                        hr_zones_df_sorted = hr_zones_df.sort_values('start_date')  # Sort ascending for time series
                        
                        fig = go.Figure()
                        fig.add_trace(go.Scatter(x=hr_zones_df_sorted['start_date'], y=hr_zones_df_sorted['zone_1_time']/60, 
                                               name='Zone 1', stackgroup='one'))
                        fig.add_trace(go.Scatter(x=hr_zones_df_sorted['start_date'], y=hr_zones_df_sorted['zone_2_time']/60, 
                                               name='Zone 2', stackgroup='one'))
                        fig.add_trace(go.Scatter(x=hr_zones_df_sorted['start_date'], y=hr_zones_df_sorted['zone_3_time']/60, 
                                               name='Zone 3', stackgroup='one'))
                        fig.add_trace(go.Scatter(x=hr_zones_df_sorted['start_date'], y=hr_zones_df_sorted['zone_4_time']/60, 
                                               name='Zone 4', stackgroup='one'))
                        fig.add_trace(go.Scatter(x=hr_zones_df_sorted['start_date'], y=hr_zones_df_sorted['zone_5_time']/60, 
                                               name='Zone 5', stackgroup='one'))
                        
                        fig.update_layout(title="Heart Rate Zone Distribution Over Time",
                                        xaxis_title="Date",
                                        yaxis_title="Time (minutes)",
                                        hovermode='x unified')
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("No heart rate zone data available. Make sure to sync activities with heart rate data.")
                
                except Exception as e:
                    st.warning(f"Could not load heart rate zone data: {str(e)}")
                    st.info("No heart rate zone data available. Make sure to sync activities with heart rate data.")
            
            with tab3:
                # Trends Analysis
                st.subheader("Performance Trends")
                
                # Resample to weekly data
                activities_df.set_index('start_date', inplace=True)
                weekly_stats = activities_df.resample('W').agg({
                    'distance_km': 'sum',
                    'moving_time_hours': 'sum',
                    'average_heartrate': 'mean',
                    'average_speed_kmh': 'mean',
                    'id': 'count'
                }).rename(columns={'id': 'activity_count'})
                
                # Distance trend
                fig = px.line(weekly_stats, y='distance_km', 
                            title="Weekly Distance Trend",
                            labels={'distance_km': 'Distance (km)', 'start_date': 'Week'})
                fig.add_scatter(y=weekly_stats['distance_km'], mode='markers', name='Weekly Distance')
                st.plotly_chart(fig, use_container_width=True)
                
                # Average speed and heart rate trends
                col1, col2 = st.columns(2)
                
                with col1:
                    fig = px.line(weekly_stats, y='average_speed_kmh',
                                title="Average Speed Trend",
                                labels={'average_speed_kmh': 'Speed (km/h)', 'start_date': 'Week'})
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    if weekly_stats['average_heartrate'].notna().any():
                        fig = px.line(weekly_stats, y='average_heartrate',
                                    title="Average Heart Rate Trend",
                                    labels={'average_heartrate': 'Heart Rate (bpm)', 'start_date': 'Week'})
                        st.plotly_chart(fig, use_container_width=True)
            
            with tab4:
                # Activities list
                st.subheader("Recent Activities")
                
                # Reset index for display
                activities_df.reset_index(inplace=True)
                
                # Select columns to display
                display_columns = ['name', 'sport_type', 'start_date', 'distance_km', 
                                 'moving_time_hours', 'average_speed_kmh', 'average_heartrate', 
                                 'total_elevation_gain']
                
                # Format the dataframe
                display_df = activities_df[display_columns].copy()
                display_df['start_date'] = display_df['start_date'].dt.strftime('%Y-%m-%d %H:%M')
                display_df['distance_km'] = display_df['distance_km'].round(2)
                display_df['moving_time_hours'] = display_df['moving_time_hours'].round(2)
                display_df['average_speed_kmh'] = display_df['average_speed_kmh'].round(1)
                display_df['average_heartrate'] = display_df['average_heartrate'].round(0)
                display_df['total_elevation_gain'] = display_df['total_elevation_gain'].round(0)
                
                # Rename columns for display
                display_df.columns = ['Name', 'Type', 'Date', 'Distance (km)', 
                                    'Time (hours)', 'Avg Speed (km/h)', 'Avg HR (bpm)', 
                                    'Elevation (m)']
                
                st.dataframe(display_df, use_container_width=True, hide_index=True)
        else:
            st.info("No activities found. Click 'Sync Activities' to fetch your data from Strava.")
    else:
        # Welcome screen
        st.header("Welcome to Bourbon Chasers Strava Tracker!")
        st.markdown("""
        This app helps track and analyze Strava activities for the Bourbon Chasers group.
        
        **Features:**
        - 📊 Comprehensive activity tracking
        - ❤️ Heart rate zone analysis
        - 📈 Performance trends
        - 👥 Multi-athlete support
        
        **Getting Started:**
        1. Click "Connect with Strava" in the sidebar
        2. Authorize the app to access your Strava data
        3. Sync your activities
        4. View your personalized dashboard
        
        All group members need to individually connect their Strava accounts for privacy and security.
        """)

if __name__ == "__main__":
    main()