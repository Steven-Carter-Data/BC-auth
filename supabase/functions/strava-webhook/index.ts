import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

interface StravaWebhookEvent {
  object_type: string;
  object_id: number;
  aspect_type: string;
  owner_id: number;
  subscription_id: number;
  event_time: number;
}

Deno.serve(async (req) => {
  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  }

  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  try {
    const supabaseUrl = Deno.env.get('SUPABASE_URL') ?? ''
    const supabaseServiceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? ''
    const verifyToken = Deno.env.get('STRAVA_VERIFY_TOKEN') ?? '05978704df8c945ee89a3eca83453cc540595530'
    const clientSecret = Deno.env.get('STRAVA_CLIENT_SECRET') ?? ''
    
    const supabase = createClient(supabaseUrl, supabaseServiceKey)

    console.log('Webhook called:', req.method, req.url)

    // Handle GET request for webhook verification
    if (req.method === 'GET') {
      const url = new URL(req.url)
      const hubMode = url.searchParams.get('hub.mode')
      const hubToken = url.searchParams.get('hub.verify_token')
      const hubChallenge = url.searchParams.get('hub.challenge')

      console.log('Verification request:', { hubMode, hubToken, hubChallenge })

      if (hubMode === 'subscribe' && hubToken === verifyToken) {
        console.log('Webhook verified successfully')
        return new Response(JSON.stringify({ 'hub.challenge': hubChallenge }), {
          headers: { 'Content-Type': 'application/json', ...corsHeaders }
        })
      } else {
        console.log('Verification failed')
        return new Response('Forbidden', { status: 403, headers: corsHeaders })
      }
    }

    // Handle POST request for webhook events
    if (req.method === 'POST') {
      const event: StravaWebhookEvent = await req.json()
      console.log('Received webhook event:', event)

      // Only process activity creation/updates
      if (event.object_type === 'activity' && (event.aspect_type === 'create' || event.aspect_type === 'update')) {
        console.log(`Processing ${event.aspect_type} for activity ${event.object_id} by athlete ${event.owner_id}`)
        
        try {
          // Get athlete's access token from database
          const { data: athlete, error: athleteError } = await supabase
            .from('athletes')
            .select('access_token, refresh_token, expires_at')
            .eq('id', event.owner_id)
            .single()

          if (athleteError || !athlete) {
            console.log('Athlete not found in database:', event.owner_id)
            return new Response('OK', { headers: corsHeaders })
          }

          // Check if token needs refresh
          let accessToken = athlete.access_token
          if (Date.now() / 1000 > athlete.expires_at - 300) { // 5 min buffer
            console.log('Refreshing access token for athlete:', event.owner_id)
            
            const refreshResponse = await fetch('https://www.strava.com/oauth/token', {
              method: 'POST',
              headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
              body: new URLSearchParams({
                client_id: Deno.env.get('STRAVA_CLIENT_ID') ?? '',
                client_secret: clientSecret,
                refresh_token: athlete.refresh_token,
                grant_type: 'refresh_token'
              })
            })

            if (refreshResponse.ok) {
              const tokenData = await refreshResponse.json()
              accessToken = tokenData.access_token

              // Update athlete's tokens in database
              await supabase
                .from('athletes')
                .update({
                  access_token: tokenData.access_token,
                  refresh_token: tokenData.refresh_token,
                  expires_at: tokenData.expires_at
                })
                .eq('id', event.owner_id)
            }
          }

          // Fetch activity details from Strava
          const activityResponse = await fetch(`https://www.strava.com/api/v3/activities/${event.object_id}`, {
            headers: { 'Authorization': `Bearer ${accessToken}` }
          })

          if (!activityResponse.ok) {
            console.error('Failed to fetch activity from Strava:', activityResponse.status)
            return new Response('OK', { headers: corsHeaders })
          }

          const activity = await activityResponse.json()
          console.log('Fetched activity details:', activity.name, activity.type)

          // Helper function to extract seconds from duration
          const getTotalSeconds = (duration: any): number => {
            if (duration === null || duration === undefined) return 0
            if (typeof duration === 'number') return duration
            return 0
          }

          // Prepare activity data for database
          const activityData = {
            id: activity.id,
            athlete_id: event.owner_id,
            name: activity.name,
            sport_type: activity.sport_type || activity.type,
            start_date: activity.start_date_local,
            distance: parseFloat(activity.distance) || 0,
            moving_time: getTotalSeconds(activity.moving_time),
            elapsed_time: getTotalSeconds(activity.elapsed_time),
            total_elevation_gain: parseFloat(activity.total_elevation_gain) || 0,
            average_heartrate: activity.average_heartrate || null,
            max_heartrate: activity.max_heartrate || null,
            average_speed: parseFloat(activity.average_speed) || 0,
            max_speed: parseFloat(activity.max_speed) || 0,
            average_watts: activity.average_watts || null,
            kilojoules: activity.kilojoules || null,
            description: activity.description || null
          }

          // Save activity to database
          const { error: activityError } = await supabase
            .from('activities')
            .upsert(activityData)

          if (activityError) {
            console.error('Error saving activity:', activityError)
          } else {
            console.log('Activity saved successfully:', activity.id)
          }

          // Fetch and save heart rate zones if available
          if (activity.has_heartrate) {
            try {
              const zonesResponse = await fetch(`https://www.strava.com/api/v3/activities/${event.object_id}/zones`, {
                headers: { 'Authorization': `Bearer ${accessToken}` }
              })

              if (zonesResponse.ok) {
                const zones = await zonesResponse.json()
                
                // Look for heart rate zones
                for (const zone of zones) {
                  if (zone.type === 'heartrate' && zone.distribution_buckets) {
                    const hrZoneData = {
                      activity_id: event.object_id,
                      zone_1_time: zone.distribution_buckets[0]?.time || 0,
                      zone_2_time: zone.distribution_buckets[1]?.time || 0,
                      zone_3_time: zone.distribution_buckets[2]?.time || 0,
                      zone_4_time: zone.distribution_buckets[3]?.time || 0,
                      zone_5_time: zone.distribution_buckets[4]?.time || 0,
                    }

                    const { error: zoneError } = await supabase
                      .from('heart_rate_zones')
                      .upsert(hrZoneData)

                    if (zoneError) {
                      console.error('Error saving heart rate zones:', zoneError)
                    } else {
                      console.log('Heart rate zones saved for activity:', event.object_id)
                    }
                    break
                  }
                }
              }
            } catch (zoneError) {
              console.log('Could not fetch heart rate zones:', zoneError)
            }
          }

        } catch (error) {
          console.error('Error processing webhook event:', error)
        }
      } else {
        console.log('Ignoring non-activity event or delete event')
      }

      return new Response('OK', { headers: corsHeaders })
    }

    return new Response('Method not allowed', { 
      status: 405, 
      headers: corsHeaders 
    })

  } catch (error) {
    console.error('Webhook error:', error)
    return new Response('Internal Server Error', { 
      status: 500, 
      headers: corsHeaders 
    })
  }
})