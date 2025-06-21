# geolocate.py
import requests

def get_coordinates(location):
    url = f"https://nominatim.openstreetmap.org/search"
    params = {"q": location + ", New York City", "format": "json"}
    headers = {"User-Agent": "NYC Danger Heatmap"}
    response = requests.get(url, params=params, headers=headers).json()
    if response:
        return float(response[0]['lat']), float(response[0]['lon'])
    return None
