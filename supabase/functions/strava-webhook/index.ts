// supabase/functions/strava-webhook/index.ts

import { serve } from "https://deno.land/std@0.168.0/http/server.ts"
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

// Your Strava webhook verification token
const VERIFY_TOKEN = Deno.env.get('STRAVA_VERIFY_TOKEN')!
const STRAVA_CLIENT_ID = Deno.env.get('STRAVA_CLIENT_ID')!
const STRAVA_CLIENT_SECRET = Deno.env.get('STRAVA_CLIENT_SECRET')!

serve(async (req) => {
  // Handle CORS preflight requests
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  try {
    const supabase = createClient(
      Deno.env.get('SUPABASE_URL') ?? '',
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? ''
    )

    // Handle webhook verification (GET request)
    if (req.method === 'GET') {
      const url = new URL(req.url)
      const mode = url.searchParams.get('hub.mode')
      const token = url.searchParams.get('hub.verify_token')
      const challenge = url.searchParams.get('hub.challenge')

      if (mode === 'subscribe' && token === VERIFY_TOKEN) {
        console.log('Webhook verified successfully')
        return new Response(challenge, {
          headers: { ...corsHeaders, 'Content-Type': 'text/plain' }
        })
      } else {
        return new Response('Verification failed', { status: 403 })
      }
    }

    // Handle webhook events (POST request)
    if (req.method === 'POST') {
      const body = await req.json()
      
      console.log('Received webhook:', JSON.stringify(body, null, 2))

      // Only process activity creation events
      if (body.object_type === 'activity' && body.aspect_type === 'create') {
        const athleteId = body.owner_id
        const activityId = body.object_id

        // Get athlete from database
        const { data: athlete, error: athleteError } = await supabase
          .from('athletes')
          .select('*')
          .eq('id', athleteId)
          .single()

        if (athleteError || !athlete) {
          console.log(`Athlete ${athleteId} not found in database`)
          return new Response('Athlete not found', { status: 200 }) // Return 200 to acknowledge webhook
        }

        // Check if token needs refresh
        let accessToken = athlete.access_token
        if (Date.now() / 1000 > athlete.expires_at - 300) { // 5 min buffer
          console.log('Refreshing token for athlete', athleteId)
          accessToken = await refreshStravaToken(athlete.refresh_token, supabase, athleteId)
        }

        // Fetch activity details from Strava
        const activityData = await fetchStravaActivity(activityId, accessToken)
        
        if (activityData) {
          // Save activity to database
          const { error: insertError } = await supabase
            .from('activities')
            .upsert({
              id: activityData.id,
              athlete_id: athleteId,
              name: activityData.name,
              sport_type: activityData.sport_type,
              start_date: activityData.start_date_local,
              distance: activityData.distance,
              moving_time: activityData.moving_time?.total_seconds || activityData.moving_time || 0,
              elapsed_time: activityData.elapsed_time?.total_seconds || activityData.elapsed_time || 0,
              total_elevation_gain: activityData.total_elevation_gain || 0,
              average_heartrate: activityData.average_heartrate,
              max_heartrate: activityData.max_heartrate,
              average_speed: activityData.average_speed || 0,
              max_speed: activityData.max_speed || 0,
              average_watts: activityData.average_watts,
              kilojoules: activityData.kilojoules,
              description: activityData.description
            })

          if (insertError) {
            console.error('Error saving activity:', insertError)
          } else {
            console.log(`Successfully saved activity ${activityId} for athlete ${athleteId}`)
          }

          // Try to fetch heart rate zones if activity has heart rate data
          if (activityData.has_heartrate) {
            try {
              const zones = await fetchStravaActivityZones(activityId, accessToken)
              if (zones) {
                const { error: zonesError } = await supabase
                  .from('heart_rate_zones')
                  .upsert({
                    activity_id: activityId,
                    ...zones
                  })
                
                if (zonesError) {
                  console.error('Error saving heart rate zones:', zonesError)
                } else {
                  console.log(`Successfully saved heart rate zones for activity ${activityId}`)
                }
              }
            } catch (error) {
              console.log('Could not fetch heart rate zones:', error)
            }
          }
        }
      }

      return new Response('Webhook processed', {
        headers: { ...corsHeaders, 'Content-Type': 'text/plain' }
      })
    }

    return new Response('Method not allowed', { status: 405 })

  } catch (error) {
    console.error('Error processing webhook:', error)
    return new Response('Internal server error', { status: 500 })
  }
})

async function refreshStravaToken(refreshToken: string, supabase: any, athleteId: number) {
  const response = await fetch('https://www.strava.com/oauth/token', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      client_id: STRAVA_CLIENT_ID,
      client_secret: STRAVA_CLIENT_SECRET,
      grant_type: 'refresh_token',
      refresh_token: refreshToken,
    }),
  })

  const tokenData = await response.json()

  // Update athlete with new tokens
  await supabase
    .from('athletes')
    .update({
      access_token: tokenData.access_token,
      refresh_token: tokenData.refresh_token,
      expires_at: tokenData.expires_at,
    })
    .eq('id', athleteId)

  return tokenData.access_token
}

async function fetchStravaActivity(activityId: number, accessToken: string) {
  const response = await fetch(`https://www.strava.com/api/v3/activities/${activityId}`, {
    headers: {
      'Authorization': `Bearer ${accessToken}`,
    },
  })

  if (!response.ok) {
    console.error('Failed to fetch activity from Strava:', response.status)
    return null
  }

  return await response.json()
}

async function fetchStravaActivityZones(activityId: number, accessToken: string) {
  const response = await fetch(`https://www.strava.com/api/v3/activities/${activityId}/zones`, {
    headers: {
      'Authorization': `Bearer ${accessToken}`,
    },
  })

  if (!response.ok) {
    return null
  }

  const zones = await response.json()
  
  // Extract heart rate zones
  for (const zone of zones) {
    if (zone.type === 'heartrate') {
      return {
        zone_1_time: zone.distribution_buckets[0]?.time || 0,
        zone_2_time: zone.distribution_buckets[1]?.time || 0,
        zone_3_time: zone.distribution_buckets[2]?.time || 0,
        zone_4_time: zone.distribution_buckets[3]?.time || 0,
        zone_5_time: zone.distribution_buckets[4]?.time || 0,
      }
    }
  }
  
  return null
}