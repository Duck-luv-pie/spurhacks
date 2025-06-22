from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def insert_event(event_type, location, lat, lon):
    response = supabase.table("events").insert({
        "type": event_type,
        "location": location,
        "lat": lat,
        "lon": lon
    }).execute()
    print("✅ Inserted into Supabase:", response)
