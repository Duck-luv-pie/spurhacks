import json
import threading
from pathlib import Path
from flask import Flask, send_file
from flask import request, jsonify
import os, requests
import sqlite3
from db_utils import insert_event

from stream_listener import listen
from nlp_parser     import extract_incident
from geolocate      import get_coordinates

from dotenv import load_dotenv
load_dotenv()   # reads .env into os.environ

import time
last_request_time = 0

# Paths
# ───────────────────────────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).resolve().parent
FRONTEND_DIR  = BASE_DIR.parent / "frontend"
EVENTS_FILE   = BASE_DIR / "events.json"

# ───────────────────────────────────────────────────────────────────────────────
app = Flask(__name__)
DB_PATH = "events.db"

@app.route("/")
def index():
    return send_file(str(FRONTEND_DIR / "landing.html"))

@app.route("/map")
def map_view():
    return send_file(str(FRONTEND_DIR / "index.html"))

@app.route("/events.json")
def get_events():
    from db_utils import supabase
    response = supabase.table("events").select("*").order("created_at", desc=True).limit(100).execute()
    return jsonify(response.data)


@app.route("/generate_news", methods=["POST"])
def generate_news():
    """
    Called by the frontend for each event:
    { type: "...", location: "..." }
    Returns JSON: { excerpt: "1-sentence teaser…" }
    """
    global last_request_time  # Add this line to declare it as global
    
    print("🔔 generate_news hit with:", request.get_json())
    data       = request.get_json()
    event_type = data.get("type")
    location   = data.get("location")

    api_key = os.getenv("GOOGLE_GEMINI_API_KEY")
    
    # Correct Gemini API endpoint
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={api_key}"
    
    headers = {
        "Content-Type": "application/json"
    }
    
    prompt = (
        f"Write a one-sentence news teaser about a {event_type} "
        f"incident at {location} in New York City."
    )
    
    # Correct request body format for Gemini API
    body = {
        "contents": [{
            "parts": [{
                "text": prompt
            }]
        }],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 100
        }
    }
    
    # Rate limiting logic
    current_time = time.time()
    if current_time - last_request_time < 4.0:
        time.sleep(1.0 - (current_time - last_request_time))
    last_request_time = time.time()
    
    try:
        resp = requests.post(url, headers=headers, json=body)
        resp.raise_for_status()  # Raises an exception for bad status codes
        
        response_data = resp.json()
        print("🔍 Gemini returned:", response_data)
        
        # Extract text from the correct response structure
        excerpt = response_data["candidates"][0]["content"]["parts"][0]["text"]
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Request error: {e}")
        excerpt = "News unavailable due to network error."
    except (KeyError, IndexError) as e:
        print(f"❌ Response parsing error: {e}")
        print("Full response:", resp.json() if 'resp' in locals() else "No response")
        excerpt = "News unavailable due to parsing error."
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        excerpt = "News unavailable."

    print("🔔 sending excerpt:", excerpt)
    return jsonify({"excerpt": excerpt})
@app.route("/generate_article", methods=["POST"])
def generate_article():
    """
    Called by the frontend for each event:
    { type: "...", location: "..." }
    Returns JSON: { article: "full article text" }
    """
    global last_request_time

    data       = request.get_json() or {}
    event_type = data.get("type", "incident")
    location   = data.get("location", "an unknown location")

    api_key = os.getenv("GOOGLE_GEMINI_API_KEY")
    url     = (
        "https://generativelanguage.googleapis.com/"
        "v1beta/models/gemini-1.5-flash-latest:generateContent"
        f"?key={api_key}"
    )

    prompt = (
        f"Write a captivating news‐style article about a {event_type} at {location} "
        "in New York City. Use vivid details, quotes, and journalistic techniques, "
        "and structure it like a real newsroom story with a headline, lead paragraph, "
        "body, and conclusion."
    )

    body = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 512   # bump this up for a longer article
        }
    }

    # simple rate-limit (shared with generate_news)
    now = time.time()
    if now - last_request_time < 4.0:
        time.sleep(4.0 - (now - last_request_time))
    last_request_time = time.time()

    try:
        resp = requests.post(url, headers={"Content-Type": "application/json"}, json=body)
        resp.raise_for_status()
        data = resp.json()
        article = data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print("❌ generate_article error:", e)
        article = "Sorry, we couldn't generate the article right now."

    return jsonify({"article": article})


# ───────────────────────────────────────────────────────────────────────────────
# Event Saving Logic
# def save_event(evt):
#     with open(EVENTS_FILE, "r+") as f:
#         try: arr = json.load(f)
#         except: arr = []
#         arr.append(evt)
#         f.seek(0); f.truncate()
#         json.dump(arr, f, indent=2)
def save_event(evt):
    insert_event(evt["type"], evt["location"], evt["lat"], evt["lon"])

# def save_event(evt):
#     conn = sqlite3.connect(DB_PATH)
#     cursor = conn.cursor()
#     cursor.execute(
#         "INSERT INTO events (type, location, lat, lon) VALUES (?, ?, ?, ?)",
#         (evt["type"], evt["location"], evt["lat"], evt["lon"])
#     )
#     conn.commit()
#     conn.close()


# ───────────────────────────────────────────────────────────────────────────────
# Stream Listener Thread
def run_listener():
    print("🎙️ Stream listener started.")
    stop = threading.Event()

    def on_txt(t):
        print(f"📝 Transcript: {t}")
        inc = extract_incident(t)
        if not inc:
            print("⚠️ No incident extracted.")
            return
        evt = {
            "type": inc["type"],
            "location": inc["location"],
            "lat": inc["lat"],
            "lon": inc["lon"]
        }
        save_event(evt)
        print("✅ Event saved:", evt)

    listen(on_txt, stop)

print(app.url_map)

# ───────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    threading.Thread(target=run_listener, daemon=True).start()
    print("🐍 Starting Flask server…")
    # bind to 127.0.0.1:5001 instead of :5000
    app.run(debug=True, host="127.0.0.1", port=5001)
