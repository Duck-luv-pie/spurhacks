# nlp_parser.py

import spacy
from transformers import pipeline
import requests
import re

# 1) Load models
nlp = spacy.load("en_core_web_sm")
classifier = pipeline(
    "zero-shot-classification",
    model="facebook/bart-large-mnli",
    device=-1  # use CPU; set to 0 if you have a GPU
)

# 2) Define your incident labels
LABELS = ["gunfire", "robbery", "assault", "fire"]

def classify_incident(text, threshold=0.6):
    """
    Use zero-shot classification to pick one of LABELS.
    Returns the label if score > threshold, else None.
    """
    out = classifier(text, candidate_labels=LABELS)
    if out["scores"][0] >= threshold:
        return out["labels"][0]
    return None

STREET_REGEX = re.compile(
    r"\b(?:[A-Za-z0-9]+(?:\s+(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard))?)\s*(?:and|&)\s*(?:[A-Za-z0-9]+(?:\s+(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard))?)\b",
    re.IGNORECASE
)



def extract_location(text):
    # 1. Try spaCy NER for real place names
    doc = nlp(text)
    for ent in doc.ents:
        if ent.label_ in ("GPE", "LOC", "FAC"):
            return ent.text

    # 2. Fallback to regex intersection pattern
    match = STREET_REGEX.search(text)
    if match:
        return match.group(0)
    
    # 3. Simple fallback: look for capitalized words near the end (like "Broadway", "Houston")
    words = [w for w in text.split() if w.istitle()]
    if words:
        return " ".join(words[-2:])


    return None

def geocode(location):
    """
    Query Nominatim (OpenStreetMap) to turn 'location' into (lat, lon).
    """
    params = {
        "q": f"{location}, New York, NY",
        "format": "json",
        "limit": 1
    }
    headers = {"User-Agent": "heatmap-hackathon/1.0"}
    resp = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params=params,
        headers=headers,
        timeout=5
    )
    if resp.ok and resp.json():
        d = resp.json()[0]
        return float(d["lat"]), float(d["lon"])
    return None

def extract_incident(text):
    print("🧠 NLP: Starting incident extraction...")

    doc = nlp(text)
    for sent in doc.sents:
        sent_text = sent.text.strip()
        print(f"🧩 Evaluating: '{sent_text}'")

        itype = classify_incident(sent_text)
        print(f"🔍 Incident type: {itype}")
        if not itype:
            continue

        loc = extract_location(sent_text)
        print(f"📍 Location: {loc}")
        if not loc:
            continue

        coords = geocode(loc)
        print(f"🗺️ Coords: {coords}")
        if not coords:
            continue

        return {"type": itype, "location": loc, "lat": coords[0], "lon": coords[1]}

    print("❌ No valid incident found in any sentence.")
    return None
