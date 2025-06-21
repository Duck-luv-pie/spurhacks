import os
import tempfile
import time
import whisper
import requests
from threading import Event
from bs4 import BeautifulSoup

# OpenMHz feed ID for NYPD 105th Precinct
OPENMHZ_FEED_ID = "5f27838a18c34482eaa31b1c"

# To avoid reprocessing same clip
last_clip_id = None



def get_latest_clip_url():
    try:
        url = "https://openmhz.com/system/nypd-105pct"
        headers = {
            "User-Agent": "Mozilla/5.0"
        }
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        # Look for the first audio clip link
        audio_tags = soup.find_all("audio")

        for audio in audio_tags:
            source = audio.find("source")
            if source and "src" in source.attrs:
                audio_url = source["src"]
                clip_id = audio_url.split("clip-")[-1].split(".")[0]
                return clip_id, audio_url
    except Exception as e:
        print(f"[ERROR] OpenMHz HTML parse failed: {e}")
    return None, None


def listen(callback, stop_event: Event):
    model = whisper.load_model("base")
    test_path = "test.m4a"  # changed from .wav

    if not os.path.exists(test_path):
        # print(f"❌ Missing test file: {test_path}")
        return

    print(f"🎧 Transcribing file: {test_path}")
    result = model.transcribe(test_path)
    # print("📝 Raw transcript:", result)
    text = result.get("text", "").strip()
    # print(f"🧾 Final transcript: '{text}'")

    if text:
        # print(f"🗣️ Transcript: {text}")
        callback(text)
    else:
        print("⚠️ No transcription detected.")

    stop_event.set()
