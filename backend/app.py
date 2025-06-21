import json
import threading
from pathlib import Path
from flask import Flask, send_file

from stream_listener import listen
from nlp_parser     import extract_incident
from geolocate      import get_coordinates

# ───────────────────────────────────────────────────────────────────────────────
# Paths
BASE_DIR      = Path(__file__).resolve().parent
FRONTEND_DIR  = BASE_DIR.parent / "frontend"
EVENTS_FILE   = BASE_DIR.parent / "backend/events.json"

# ───────────────────────────────────────────────────────────────────────────────
app = Flask(__name__)

@app.route("/")
def index():
    return send_file(str(FRONTEND_DIR / "index.html"))

@app.route("/events.json")
def serve_events():
    return send_file(str(EVENTS_FILE))

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

# ───────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    threading.Thread(target=run_listener, daemon=True).start()
    print("🐍 Starting Flask server…")
    app.run(debug=True, use_reloader=False)
