import os
from datetime import datetime
import requests
import pytz
from timezonefinder import TimezoneFinder
from dotenv import load_dotenv

load_dotenv()

def fetch_weather(lat=28.5383, lon=-81.3792, exclude="minutely", units="metric", lang="en"):
    api_key = os.getenv('OPENWEATHER_API_KEY')
    if not api_key:
        raise ValueError("API key not found. Please set OPENWEATHER_API_KEY in your .env file.")
    url = f"https://api.openweathermap.org/data/3.0/onecall?lat={lat}&lon={lon}&appid={api_key}&units={units}&lang={lang}"
    if exclude:
        url += f"&exclude={exclude}"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

def get_time(lat=28.5383, lon=-81.3792):
    tf = TimezoneFinder()
    tz_name = tf.timezone_at(lat=lat, lng=lon)
    if not tz_name:
        raise ValueError("Time zone could not be determined for the given coordinates.")
    local_tz = pytz.timezone(tz_name)
    local_time = datetime.now(local_tz)
    return local_time.strftime("%H:%M:%S")

def get_tools():
    return [
        {
            "type": "function",
            "function": {
                "name": "fetch_weather",
                "description": "Fetch current weather and forecast data...",
                "strict": True,
                "parameters": {
                    "type": "object",
                    "required": ["lat", "lon", "exclude", "units", "lang"],
                    "properties": {
                        "lat": {"type": "number", "description": "Latitude..."},
                        "lon": {"type": "number", "description": "Longitude..."},
                        "exclude": {"type": "string", "description": "Data to exclude..."},
                        "units": {"type": "string", "description": "Units of measurement..."},
                        "lang": {"type": "string", "description": "Language of the response..."}
                    },
                    "additionalProperties": False
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_time",
                "description": "Fetch the current time based on location...",
                "strict": True,
                "parameters": {
                    "type": "object",
                    "required": ["lat", "lon"],
                    "properties": {
                        "lat": {"type": "number", "description": "Latitude..."},
                        "lon": {"type": "number", "description": "Longitude..."}
                    },
                    "additionalProperties": False
                }
            }
        }
    ]

def get_available_functions():
    return {
        "fetch_weather": fetch_weather,
        "get_time": get_time
    }
