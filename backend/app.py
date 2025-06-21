import json
import threading
from pathlib import Path
from flask import Flask, send_file
from flask import request, jsonify
import os, requests

from stream_listener import listen
from nlp_parser     import extract_incident
from geolocate      import get_coordinates

from dotenv import load_dotenv
load_dotenv()   # reads .env into os.environ


# ───────────────────────────────────────────────────────────────────────────────
# Paths
BASE_DIR      = Path(__file__).resolve().parent
FRONTEND_DIR  = BASE_DIR.parent / "frontend"
EVENTS_FILE   = BASE_DIR / "events.json"

# ───────────────────────────────────────────────────────────────────────────────
app = Flask(__name__)

@app.route("/")
def index():
    return send_file(str(FRONTEND_DIR / "index.html"))

@app.route("/events.json")
def serve_events():
    return send_file(str(EVENTS_FILE))

@app.route("/generate_news", methods=["POST"])
def generate_news():
    """
    Called by the frontend for each event:
    { type: "...", location: "..." }
    Returns JSON: { excerpt: "1-sentence teaser…" }
    """
    data       = request.get_json()
    event_type = data.get("type")
    location   = data.get("location")

    api_key = os.getenv("GOOGLE_GEMINI_API_KEY")
    url     = "https://generativelanguage.googleapis.com/v1beta2/models/chat-bison-001:generateMessage"
    headers = {
      "Authorization": f"Bearer {api_key}",
      "Content-Type":  "application/json"
    }
    prompt = (
      f"Write a one-sentence news teaser about a {event_type} "
      f"incident at {location} in New York City."
    )
    body = {
      "prompt": {"text": prompt},
      "temperature": 0.7,
      "candidate_count": 1
    }

    resp = requests.post(url, headers=headers, json=body)
    if resp.ok:
        excerpt = resp.json()["candidates"][0]["content"]
    else:
        excerpt = "News unavailable."

    return jsonify({ "excerpt": excerpt })

# ───────────────────────────────────────────────────────────────────────────────
# Event Saving Logic
def save_event(evt):
    with open(EVENTS_FILE, "r+") as f:
        try: arr = json.load(f)
        except: arr = []
        arr.append(evt)
        f.seek(0); f.truncate()
        json.dump(arr, f, indent=2)

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
    app.run(debug=True)
