import csv
import io
import json
import math
import os
import re
import secrets
import smtplib
import sqlite3
import warnings
from collections import Counter, defaultdict
import time
import hashlib
from datetime import datetime, timedelta
from email.message import EmailMessage
from functools import wraps
import threading

import requests
from flask import (
    Flask,
    Response,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
try:
    from flask_compress import Compress
except Exception:
    Compress = None
from werkzeug.security import check_password_hash, generate_password_hash

# Workaround for protobuf/tensorflow compatibility in dev environments
import os as _os_for_proto
if not _os_for_proto.environ.get("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"):
    _os_for_proto.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOTENV_PATH = os.path.join(BASE_DIR, ".env")

try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False
    def load_dotenv(*args, **kwargs):
        return False


def _manual_load_dotenv(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[len("export "):]
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
        return True
    except FileNotFoundError:
        return False


def _load_environment():
    if DOTENV_AVAILABLE:
        try:
            return load_dotenv(DOTENV_PATH, override=True)
        except TypeError:
            return load_dotenv(DOTENV_PATH)
    return _manual_load_dotenv(DOTENV_PATH)


_load_environment()

# Persistent AI cache file to survive restarts (fingerprint -> {ts, text})
AI_CACHE_FILE = os.path.join(BASE_DIR, ".ai_cache.json")
try:
    with open(AI_CACHE_FILE, "r", encoding="utf-8") as _f:
        _ai_cache = {k: (v.get("ts", 0), v.get("text", "")) for k, v in json.load(_f).items()}
except Exception:
    _ai_cache = {}

APP_NAME = "AgriNexus"
DATABASE = os.path.join(BASE_DIR, "fertilizer.db")
DATA_DIR = os.path.join(BASE_DIR, "data")
CROP_DATASET = os.path.join(DATA_DIR, "crop_recommendation.csv")
FERTILIZER_DATASET = os.path.join(DATA_DIR, "fertilizer_prediction.csv")

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", secrets.token_hex(32))
# Serve static assets with long cache headers to improve repeat load performance
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 31536000  # one year
# Enable template auto-reload during development so changes show immediately
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.jinja_env.auto_reload = True
# Enable gzip/deflate compression for responses where appropriate (optional)
if Compress:
    try:
        Compress(app)
    except Exception:
        # If Flask-Compress fails to initialize, continue without compression
        pass

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
SMTP_SENDER = os.getenv("SMTP_SENDER", SMTP_USERNAME or "noreply@example.com")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
OPENWEATHER_BASE_URL = os.getenv("OPENWEATHER_BASE_URL", "https://api.openweathermap.org")
GEMINI_MODEL = None
GEMINI_INIT_ERROR = None
if GEMINI_API_KEY:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            import google.generativeai as genai

        genai.configure(api_key=GEMINI_API_KEY)
        GEMINI_MODEL = genai.GenerativeModel(os.getenv("GEMINI_MODEL", "gemini-1.5-flash"))
    except Exception as exc:
        GEMINI_MODEL = None
        GEMINI_INIT_ERROR = str(exc)

# Optional local ML model integration (AgriGo artifacts)
try:
    from backend import ml_models
    ML_MODELS_AVAILABLE = True
except Exception:
    ML_MODELS_AVAILABLE = False

FEATURES = ["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]
SATELLITE_FIELDS = ["ndvi", "evi", "surface_temp", "precipitation"]
SOIL_TYPES = ["Black", "Clayey", "Loamy", "Red", "Sandy", "Silty", "Peaty"]
CROP_TYPES = [
    "Apple",
    "Banana",
    "Barley",
    "Blackgram",
    "Chickpea",
    "Coconut",
    "Coffee",
    "Cotton",
    "Grapes",
    "Ground Nuts",
    "Jute",
    "Kidneybeans",
    "Lentil",
    "Maize",
    "Mango",
    "Millets",
    "Mothbeans",
    "Mungbean",
    "Muskmelon",
    "Oil seeds",
    "Orange",
    "Paddy",
    "Papaya",
    "Pigeonpeas",
    "Pomegranate",
    "Pulses",
    "Rice",
    "Soybean",
    "Sugarcane",
    "Tobacco",
    "Watermelon",
    "Wheat",
]

FERTILIZER_GUIDE = {
    "Urea": {
        "focus": "nitrogen correction",
        "timing": "Split into two to three applications around active vegetative growth.",
    },
    "DAP": {
        "focus": "phosphorus and starter nitrogen",
        "timing": "Place near the root zone before sowing or during early establishment.",
    },
    "10-26-26": {
        "focus": "balanced phosphorus and potassium support",
        "timing": "Use at basal application where P and K are both limiting.",
    },
    "14-35-14": {
        "focus": "high phosphorus with balanced N and K",
        "timing": "Prefer during root development and early crop establishment.",
    },
    "17-17-17": {
        "focus": "balanced NPK maintenance",
        "timing": "Apply when soil nutrients are moderately balanced but total fertility is low.",
    },
    "20-20": {
        "focus": "nitrogen and phosphorus support",
        "timing": "Use for crops needing canopy growth and root reinforcement.",
    },
    "28-28": {
        "focus": "strong nitrogen and phosphorus correction",
        "timing": "Use carefully where both N and P are deficient; avoid overuse in high pH soil.",
    },
    "Organic": {
        "focus": "soil structure and slow nutrient release",
        "timing": "Incorporate before planting or as composted side dressing.",
    },
}

BASE_YIELD_T_HA = {
    "apple": 18.0,
    "banana": 32.0,
    "barley": 3.6,
    "blackgram": 1.1,
    "chickpea": 1.4,
    "coconut": 9.0,
    "coffee": 1.2,
    "cotton": 2.5,
    "grapes": 16.0,
    "ground nuts": 2.2,
    "jute": 2.7,
    "kidneybeans": 1.7,
    "lentil": 1.2,
    "maize": 5.8,
    "mango": 8.0,
    "millets": 2.0,
    "mothbeans": 0.9,
    "mungbean": 1.0,
    "muskmelon": 20.0,
    "oil seeds": 1.6,
    "orange": 15.0,
    "paddy": 4.5,
    "papaya": 38.0,
    "pigeonpeas": 1.3,
    "pomegranate": 12.0,
    "pulses": 1.2,
    "rice": 4.6,
    "soybean": 2.7,
    "sugarcane": 72.0,
    "tobacco": 2.1,
    "watermelon": 28.0,
    "wheat": 3.8,
}

CROP_MARKET_PRICE_PER_TON = {
    "apple": 180000,
    "banana": 22000,
    "barley": 19000,
    "blackgram": 78000,
    "chickpea": 70000,
    "coconut": 30000,
    "coffee": 140000,
    "cotton": 52000,
    "grapes": 120000,
    "ground nuts": 85000,
    "jute": 36000,
    "kidneybeans": 68000,
    "lentil": 62000,
    "maize": 23000,
    "mango": 95000,
    "millets": 25000,
    "mothbeans": 76000,
    "mungbean": 78000,
    "muskmelon": 32000,
    "oil seeds": 48000,
    "orange": 42000,
    "paddy": 22000,
    "papaya": 28000,
    "pigeonpeas": 71000,
    "pomegranate": 110000,
    "pulses": 60000,
    "rice": 23000,
    "soybean": 42000,
    "sugarcane": 4200,
    "tobacco": 95000,
    "watermelon": 26000,
    "wheat": 22000,
}


YIELD_RANGE_PATTERNS = [
    re.compile(
        r"(?P<low>\d+(?:\.\d+)?)\s*(?:-|to|and|–|—)\s*(?P<high>\d+(?:\.\d+)?)\s*(?P<unit>kg/ha|kg per hectare|t/ha|tons?/ha|tons? per hectare)",
        re.IGNORECASE,
    ),
    re.compile(
        r"between\s+(?P<low>\d+(?:\.\d+)?)\s*(?:-|to|and|–|—)\s*(?P<high>\d+(?:\.\d+)?)\s*(?P<unit>kg/ha|kg per hectare|t/ha|tons?/ha|tons? per hectare)",
        re.IGNORECASE,
    ),
]


def connect_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                farm_name TEXT,
                location TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS password_reset_otps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                otp_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                message TEXT NOT NULL,
                provider TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                soil TEXT,
                weather TEXT,
                fertilizer TEXT,
                amount REAL,
                crop TEXT,
                predicted_yield TEXT,
                description TEXT,
                raw_response TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_cache (
                fingerprint TEXT PRIMARY KEY,
                provider TEXT,
                result_text TEXT,
                cached_at REAL
            )
            """
        )

        required_columns = {
            "prediction_type": "TEXT DEFAULT 'yield'",
            "location": "TEXT",
            "market_price": "TEXT",
            "nitrogen": "REAL",
            "phosphorus": "REAL",
            "potassium": "REAL",
            "ph": "REAL",
            "temperature": "REAL",
            "humidity": "REAL",
            "rainfall": "REAL",
            "moisture": "REAL",
            "risk_level": "TEXT",
            "confidence": "REAL",
            "recommendation": "TEXT",
            "ai_provider": "TEXT",
            "ai_enriched": "INTEGER DEFAULT 0",
            "created_at": "TEXT",
            "user_id": "INTEGER",
        }
        existing = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(predictions)").fetchall()
        }
        for column, definition in required_columns.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE predictions ADD COLUMN {column} {definition}")
        conn.commit()


def parse_float(value, field, minimum=None, maximum=None):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be a valid number.")
    if minimum is not None and number < minimum:
        raise ValueError(f"{field} must be at least {minimum}.")
    if maximum is not None and number > maximum:
        raise ValueError(f"{field} must be at most {maximum}.")
    return number


def parse_optional_float(value):
    if value is None or str(value).strip() == "":
        return None
    return float(value)


def apply_sensor_overrides(inputs, sensor_source):
    if not isinstance(sensor_source, dict):
        return inputs

    for field in ("temperature", "humidity", "rainfall", "moisture"):
        sensor_key = f"sensor_{field}"
        raw_value = sensor_source.get(sensor_key, sensor_source.get(field))
        if raw_value is None or str(raw_value).strip() == "":
            continue
        try:
            inputs[field] = float(raw_value)
        except (TypeError, ValueError):
            pass

    if sensor_source.get("sensor_location"):
        inputs["location"] = str(sensor_source.get("sensor_location"))

    for field in ("sensor_id", "sensor_timestamp"):
        if sensor_source.get(field):
            inputs[field] = str(sensor_source.get(field))

    return inputs


def apply_satellite_overrides(inputs, satellite_source):
    if not isinstance(satellite_source, dict):
        return inputs

    for field in SATELLITE_FIELDS:
        satellite_key = f"satellite_{field}"
        raw_value = satellite_source.get(satellite_key, satellite_source.get(field))
        if raw_value is None or str(raw_value).strip() == "":
            continue
        try:
            inputs[satellite_key] = float(raw_value)
        except (TypeError, ValueError):
            pass

    return inputs


def db_get_ai_cache(fingerprint):
    try:
        with connect_db() as conn:
            row = conn.execute(
                "SELECT fingerprint, provider, result_text, cached_at FROM ai_cache WHERE fingerprint = ?",
                (fingerprint,),
            ).fetchone()
            if row:
                return dict(row)
    except Exception:
        return None
    return None


def db_set_ai_cache(fingerprint, provider, result_text, ts=None):
    ts = ts or time.time()
    try:
        with connect_db() as conn:
            conn.execute(
                "REPLACE INTO ai_cache (fingerprint, provider, result_text, cached_at) VALUES (?, ?, ?, ?)",
                (fingerprint, provider, result_text, ts),
            )
            conn.commit()
    except Exception:
        pass


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    with connect_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def calculate_area_from_location(location_name, radius_m=1000):
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    geocode_url = "https://maps.googleapis.com/maps/api/geocode/json"
    geocode_params = {"address": location_name, "key": api_key} if api_key else {"address": location_name}
    geocode_response = requests.get(geocode_url, params=geocode_params, timeout=10)
    geocode_response.raise_for_status()
    geocode_payload = geocode_response.json()

    if geocode_payload.get("status") != "OK" or not geocode_payload.get("results"):
        return {
            "location": location_name,
            "address": location_name,
            "lat": 0.0,
            "lng": 0.0,
            "radius_m": radius_m,
            "area_sq_m": math.pi * (radius_m ** 2),
            "area_ha": math.pi * (radius_m ** 2) / 10000,
            "area_acres": math.pi * (radius_m ** 2) / 4046.8564224,
        }

    result = geocode_payload["results"][0]
    location = result["geometry"]["location"]
    lat = location["lat"]
    lng = location["lng"]
    area_sq_m = math.pi * (radius_m ** 2)
    area_acres = area_sq_m / 4046.8564224
    return {
        "location": location_name,
        "address": result.get("formatted_address", location_name),
        "lat": lat,
        "lng": lng,
        "radius_m": radius_m,
        "area_sq_m": area_sq_m,
        "area_ha": area_sq_m / 10000,
        "area_acres": area_acres,
    }


@app.route("/geocode")
def geocode_location():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify(success=False, error="No location provided."), 400

    coord_match = re.match(r"^\s*(-?\d{1,3}(?:\.\d+)?)\s*,\s*(-?\d{1,3}(?:\.\d+)?)\s*$", query)
    if coord_match:
        lat = float(coord_match.group(1))
        lng = float(coord_match.group(2))
        if lat < -90 or lat > 90 or lng < -180 or lng > 180:
            return jsonify(success=False, error="Coordinates are out of range."), 400
        return jsonify(success=True, address=f"{lat},{lng}", lat=lat, lng=lng, display_name=f"{lat},{lng}")

    try:
        location_data = calculate_area_from_location(query, radius_m=0)
    except requests.RequestException:
        return jsonify(success=False, error="Location lookup failed."), 502

    if location_data["lat"] == 0.0 and location_data["lng"] == 0.0 and location_data["address"] == query:
        return jsonify(success=False, error="Location not found."), 404

    return jsonify(
        success=True,
        address=location_data["address"],
        lat=location_data["lat"],
        lng=location_data["lng"],
        display_name=location_data["address"],
    )


@app.route("/live-weather")
def live_weather():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify(success=False, error="No location provided."), 400

    weather_data = fetch_live_weather(query)
    if not weather_data:
        return jsonify(success=False, error="Unable to fetch live weather for this location."), 502

    return jsonify(success=True, weather=weather_data)


def calculate_polygon_area_sq_m(points):
    if len(points) < 3:
        raise ValueError("At least three points are required to form a polygon.")

    if points[0] == points[-1]:
        points = points[:-1]
        if len(points) < 3:
            raise ValueError("At least three unique points are required to form a polygon.")

    earth_radius_m = 6_378_137.0
    total = 0.0
    for index in range(len(points)):
        lat1, lng1 = points[index]
        lat2, lng2 = points[(index + 1) % len(points)]
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lng = math.radians(lng2 - lng1)
        if delta_lng > math.pi:
            delta_lng -= 2 * math.pi
        elif delta_lng < -math.pi:
            delta_lng += 2 * math.pi
        total += delta_lng * (2 + math.sin(lat1_rad) + math.sin(lat2_rad))

    return abs(total) * (earth_radius_m ** 2) / 2.0


def ensure_active_user_id():
    user_id = session.get("user_id")
    if user_id:
        return user_id

    with connect_db() as conn:
        row = conn.execute(
            "SELECT id FROM users WHERE email = ?",
            ("guest@local",),
        ).fetchone()
        if row:
            user_id = row["id"]
        else:
            cursor = conn.execute(
                """
                INSERT INTO users (name, email, password_hash, farm_name, location, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "Guest User",
                    "guest@local",
                    "guest-password",
                    None,
                    None,
                    datetime.utcnow().isoformat(timespec="seconds"),
                ),
            )
            conn.commit()
            user_id = cursor.lastrowid

    session["user_id"] = user_id
    return user_id


def send_password_reset_email(to_email, otp):
    if not SMTP_HOST or not SMTP_USERNAME or not SMTP_PASSWORD:
        return False

    message = EmailMessage()
    message["Subject"] = "Your password reset OTP"
    message["From"] = SMTP_SENDER
    message["To"] = to_email
    message.set_content(
        f"Your password reset OTP is {otp}. It will expire in 10 minutes."
    )

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            if SMTP_USE_TLS:
                server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(message)
        return True
    except Exception:
        return False


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Sign in to manage your farm plans.")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


LANGUAGES = {
    "en": "English",
    "ne": "नेपाली",
}

TRANSLATIONS = {
    "ne": {
        "Language": "भाषा",
        "English": "अंग्रेजी",
        "Nepali": "नेपाली",
        "Yield Planner": "उपज योजनाकर्ता",
        "Crop Advisor": "बाली सल्लाहकार",
        "Fertilizer": "मल",
        "Chatbot": "च्याटबोट",
        "History": "इतिहास",
        "Account": "खाता",
        "Logout": "लगआउट",
        "Login": "लगइन",
        "Register": "दर्ता",
        "Disease": "रोग",
        "Area": "क्षेत्र",
        "About": "बारेमा",
        "Developer": "विकासकर्ता",
        "Farm decision workspace": "कृषि निर्णय कार्यस्थान",
        "Estimate yield, compare fertilizer fit, rank crop options, and manage field decisions inside a private farm workspace.": "उपज अनुमान गर्नुहोस्, मलको उपयुक्तता तुलना गर्नुहोस्, बाली विकल्पहरू क्रमबद्ध गर्नुहोस्, र निजी कृषि कार्यस्थानमा निर्णयहरू व्यवस्थापन गर्नुहोस्।",
        "Create an account to save plans, export history, and use the farm chatbot.": "योजनाहरू सुरक्षित गर्न, इतिहास निर्यात गर्न, र कृषि च्याटबोट प्रयोग गर्न खाता बनाउनुहोस्।",
        "Field Inputs": "खेतको विवरण",
        "Current Fertilizer": "हालको मल",
        "Crop": "बाली",
        "Soil": "माटो",
        "Observed Weather": "अवलोकन गरिएको मौसम",
        "Location (district/state)": "स्थान (जिल्ला/प्रदेश)",
        "Enter district/state": "जिल्ला/प्रदेश लेख्नुहोस्",
        "Fertilizer Rate (kg/ha)": "मलको दर (kg/ha)",
        "Nitrogen (N)": "नाइट्रोजन (N)",
        "Phosphorus (P)": "फस्फोरस (P)",
        "Potassium (K)": "पोटासियम (K)",
        "Soil pH": "माटो pH",
        "Temperature (C)": "तापक्रम (C)",
        "Humidity (%)": "आर्द्रता (%)",
        "Rainfall (mm)": "वर्षा (mm)",
        "Soil Moisture (%)": "माटोको चिस्यान (%)",
        "Generate Plan": "योजना तयार गर्नुहोस्",
        "Total Plans": "जम्मा योजनाहरू",
        "Most Planned Crop": "सबैभन्दा धेरै योजना गरिएको बाली",
        "Average Confidence": "औसत विश्वास",
        "AI Enrichment": "AI समृद्धि",
        "Recent plans": "हालका योजनाहरू",
        "Saved Decisions": "सुरक्षित निर्णयहरू",
        "No saved plans yet.": "अहिलेसम्म कुनै सुरक्षित योजना छैन।",
        "Find best crops": "राम्रो बाली खोज्नुहोस्",
        "Recommend fertilizer": "मल सिफारिस गर्नुहोस्",
        "Export CSV": "CSV निर्यात गर्नुहोस्",
        "Sell crop online": "बाली अनलाइन बेच्नुहोस्",
        "Quick sell the recommended crop": "सिफारिस गरिएको बाली छिटो बेच्नुहोस्",
        "Sell crop produce online": "बाली उत्पादन अनलाइन बेच्नुहोस्",
        "Buy crop product online": "बाली उत्पादन अनलाइन किन्नुहोस्",
        "Quick buy the recommended crop product": "सिफारिस गरिएको बाली उत्पादन छिटो किन्नुहोस्",
        "Buy fertilizer online": "मल अनलाइन किन्नुहोस्",
        "Quick buy the recommended fertilizer": "सिफारिस गरिएको मल छिटो किन्नुहोस्",
        "Amazon": "Amazon",
        "Flipkart": "Flipkart",
        "Google Search": "Google Search",
        "Sell online": "अनलाइन बेच्नुहोस्",
        "Buy online": "अनलाइन किन्नुहोस्",
        "Crop advisor": "बाली सल्लाहकार",
        "Match crops to soil and weather": "बालीलाई माटो र मौसमसँग मिलाउनुहोस्",
        "Recommend Crops": "बाली सिफारिस गर्नुहोस्",
        "Yield planner": "उपज योजनाकर्ता",
        "Secure farm workspace": "सुरक्षित कृषि कार्यस्थान",
        "Create your account": "आफ्नो खाता बनाउनुहोस्",
        "Welcome back": "फेरि स्वागत छ",
        "Reset your access": "आफ्नो पहुँच रिसेट गर्नुहोस्",
        "Register": "दर्ता",
        "Login": "लगइन",
        "Forgot Password": "पासवर्ड बिर्सनुभयो",
        "Reset Password": "पासवर्ड रिसेट गर्नुहोस्",
        "Start managing fields": "खेत व्यवस्थापन सुरु गर्नुहोस्",
        "Access your workspace": "आफ्नो कार्यस्थान खोल्नुहोस्",
        "Recover your account": "आफ्नो खाता पुनःप्राप्त गर्नुहोस्",
        "Name": "नाम",
        "Email": "इमेल",
        "Password": "पासवर्ड",
        "Farm Name": "खेतको नाम",
        "Location": "स्थान",
        "Send OTP": "OTP पठाउनुहोस्",
        "Create Account": "खाता बनाउनुहोस्",
        "Already have an account?": "पहिल्यै खाता छ?",
        "New here?": "नयाँ हुनुहुन्छ?",
        "Create an account": "खाता बनाउनुहोस्",
        "Back to login": "लगइनमा फर्कनुहोस्",
        "Ready for a field question": "खेतसँग सम्बन्धित प्रश्नका लागि तयार",
        "Ask about fertilizer timing, crop choice, risk level, or how to interpret a saved plan.": "मलको समय, बाली छनोट, जोखिम स्तर, वा सुरक्षित योजनाको अर्थबारे सोध्नुहोस्।",
        "Ask: What should I improve before sowing rice?": "जस्तै: धान रोप्नु अघि के सुधार गर्नुपर्छ?",
        "Send": "पठाउनुहोस्",
        "Saved field plan": "सुरक्षित खेत योजना",
        "New Plan": "नयाँ योजना",
        "Yield Range": "उपज दायरा",
        "Market Value": "बजार मूल्य",
        "Risk": "जोखिम",
        "Confidence": "विश्वास",
        "Action plan": "कार्य योजना",
        "Recommended Next Steps": "सुझाव गरिएका अर्को चरणहरू",
        "Field snapshot": "खेतको सारांश",
        "Inputs": "इनपुटहरू",
        "Location": "स्थान",
        "NPK": "NPK",
        "pH": "pH",
        "Temperature": "तापक्रम",
        "Humidity": "आर्द्रता",
        "Rainfall": "वर्षा",
        "Moisture": "चिस्यान",
        "Rate": "दर",
        "AI note": "AI टिप्पणी",
        "Enrichment": "समृद्ध विवरण",
        "Decision history": "निर्णय इतिहास",
        "Saved Predictions": "सुरक्षित भविष्यवाणीहरू",
        "Total": "जम्मा",
        "Top Crop": "शीर्ष बाली",
        "Avg Confidence": "औसत विश्वास",
        "High Risk": "उच्च जोखिम",
        "No saved predictions yet.": "अहिलेसम्म कुनै सुरक्षित भविष्यवाणी छैन।",
        "Deep learning diagnosis": "डीप लर्निङ निदान",
        "Crop Disease Detection": "बाली रोग पत्ता लगाउने",
        "Upload a leaf photo to detect diseases using trained deep learning models.": "प्रशिक्षित डीप लर्निङ मोडेल प्रयोग गरेर रोग पत्ता लगाउन पातको फोटो अपलोड गर्नुहोस्।",
        "Supported crops:": "समर्थित बालीहरू:",
        "Select the crop type and upload a clear leaf image": "बालीको प्रकार चयन गर्नुहोस् र स्पष्ट पातको फोटो अपलोड गर्नुहोस्",
        "Select Crop": "बाली छान्नुहोस्",
        "Detect Disease": "रोग पत्ता लगाउनुहोस्",
        "Diagnosis Result": "निदान नतिजा",
        "Healthy Crop": "स्वस्थ बाली",
        "Disease Detected": "रोग भेटियो",
        "Treatment Advice": "उपचार सल्लाह",
        "Suggested fertilizer:": "सुझाव गरिएको मल:",
        "Analyze Another": "अर्को विश्लेषण गर्नुहोस्",
        "Polygon area": "बहुभुज क्षेत्र",
        "Calculate Area": "क्षेत्र गणना गर्नुहोस्",
        "Click around the edge of the field to create coordinates, form a polygon, and calculate the geodesic area.": "क्षेत्रको किनारामा बिन्दु राखेर निर्देशांक बनाउनुहोस्, बहुभुज तयार गर्नुहोस्, र भू-आधारित क्षेत्रफल गणना गर्नुहोस्।",
        "Search location or enter latitude,longitude": "स्थान खोज्नुहोस् वा अक्षांश,देशान्तर प्रविष्ट गर्नुहोस्",
        "Search": "खोज्नुहोस्",
        "Zoom in as much as possible, place points along the exact edge of the field, add more points for curved or irregular boundaries, and close the polygon at the starting point.": "जति सक्दो नजिक जूम गर्नुहोस्, खेतको ठीक किनारामा बिन्दु राख्नुहोस्, घुमाउरो वा अनियमित सीमाका लागि थप बिन्दु थप्नुहोस्, र सुरु बिन्दुमा बहुभुज बन्द गर्नुहोस्।",
        "If you search a location, the app can automatically create a simple field-shaped outline around that point.": "यदि तपाईंले स्थान खोज्नुभयो भने, एपले त्यही बिन्दु वरिपरि साधारण खेत-जस्तो रूपरेखा स्वतः बनाउन सक्छ।",
        "Accuracy method": "शुद्धता विधि",
        "Manual polygon on satellite map": "स्याटेलाइट नक्सामा म्यानुअल बहुभुज",
        "GPS walking around the field": "खेत वरिपरि GPS हिँडेर",
        "Survey-grade GPS (RTK)": "सर्भे-ग्रेड GPS (RTK)",
        "Google Maps screenshot measurement": "Google Maps स्क्रिनसट मापन",
        "Satellite": "स्याटेलाइट",
        "Street": "सडक",
        "Hybrid": "हाइब्रिड",
        "Add Point": "बिन्दु थप्नुहोस्",
        "Move Map": "नक्सा सार्नुहोस्",
        "Use My Location": "मेरो स्थान प्रयोग गर्नुहोस्",
        "Clear": "खाली गर्नुहोस्",
        "Close Polygon": "बहुभुज बन्द गर्नुहोस्",
        "Tap the map to start marking your field boundary.": "आफ्नो खेतको सीमाना चिन्ह लगाउन नक्सामा ट्याप गर्नुहोस्।",
        "Selected coordinates: none": "छानिएका निर्देशांक: छैन",
        "Result": "नतिजा",
        "Polygon Area": "बहुभुज क्षेत्रफल",
        "Area (sq m)": "क्षेत्रफल (वर्ग मिटर)",
        "Points": "बिन्दुहरू",
        "The area is calculated geodesically from the marked polygon points.": "चिन्ह लगाइएका बहुभुज बिन्दुबाट क्षेत्रफल भू-आधारित रूपमा गणना गरिन्छ।",
        "About": "बारेमा",
        "AI agronomy chatbot": "AI कृषि च्याटबोट",
        "Ask about your field plans": "आफ्नो खेत योजनाबारे सोध्नुहोस्",
        "Gemini answers first when configured. Groq automatically handles fallback for fast responses.": "कन्फिगर गरिएको भए Gemini पहिले जवाफ दिन्छ। छिटो प्रतिक्रियाका लागि Groq स्वतः फलब्याक हुन्छ।",
        "On": "अन",
        "Off": "अफ",
        "You": "तपाईं",
        "Ready for a field question": "खेतसम्बन्धी प्रश्नका लागि तयार",
        "Ask about fertilizer timing, crop choice, risk level, or how to interpret a saved plan.": "मलको समय, बाली छनोट, जोखिम स्तर, वा सुरक्षित योजनाको अर्थबारे सोध्नुहोस्।",
        "Fertilizer advisor": "मल सल्लाहकार",
        "Choose a nutrient strategy": "पोषक तत्त्व रणनीति छान्नुहोस्",
        "Application Plan": "प्रयोग योजना",
        "Advisor recommendation": "सल्लाहकार सिफारिस",
        "Primary focus": "मुख्य ध्यान",
        "Timing": "समय",
        "N gap": "N अन्तर",
        "P gap": "P अन्तर",
        "K gap": "K अन्तर",
        "Submit field conditions to generate a fertilizer recommendation.": "मल सिफारिस पाउन खेतका विवरणहरू पेश गर्नुहोस्।",
        "Submit soil and climate values to rank crop options.": "बाली विकल्पहरू क्रमबद्ध गर्न माटो र मौसमका मानहरू पेश गर्नुहोस्।",
    }
}


def get_language():
    language = session.get("language", "en")
    return language if language in LANGUAGES else "en"


def translate(text):
    return TRANSLATIONS.get(get_language(), {}).get(text, text)


@app.route("/language/<lang>")
def set_language(lang):
    if lang in LANGUAGES:
        session["language"] = lang
    return redirect(request.referrer or url_for("index"))


@app.context_processor
def inject_user():
    language = get_language()
    return {
        "current_user": current_user(),
        "lang": language,
        "languages": LANGUAGES,
        "language_name": LANGUAGES[language],
        "t": translate,
    }

UNPROTECTED_ENDPOINTS = {
    "login",
    "register",
    "forgot_password",
    "reset_password",
    "set_language",
    "static",
    "geocode_location",
    "live_weather",
}


@app.before_request
def require_login():
    if request.endpoint in UNPROTECTED_ENDPOINTS or request.endpoint is None:
        return
    if session.get("user_id"):
        return
    if request.path.startswith("/api"):
        return jsonify(success=False, error="Authentication required"), 401
    return redirect(url_for("login", next=request.path))


def title_crop(crop):
    return str(crop).replace("_", " ").title()


def summarize_yield_text(predicted_yield, raw_response=None, max_length=72):
    for candidate in (predicted_yield, raw_response):
        if not candidate:
            continue
        text = str(candidate).replace("\r", " ").replace("\n", " ").strip()
        for pattern in YIELD_RANGE_PATTERNS:
            match = pattern.search(text)
            if match:
                low = match.group("low")
                high = match.group("high")
                unit = match.group("unit").lower()
                if "ton" in unit:
                    unit = "t/ha"
                elif "kg" in unit:
                    unit = "kg/ha"
                return f"{low} - {high} {unit}"
        if len(text) <= max_length:
            return text
        return text[: max_length - 1].rstrip() + "…"
    return "-"


def enrich_prediction_row(row):
    item = dict(row)
    item["predicted_yield_display"] = summarize_yield_text(
        item.get("predicted_yield"), item.get("raw_response")
    )
    prediction_type = str(item.get("prediction_type") or "yield").lower()
    type_labels = {
        "yield": "Yield Planner",
        "crop": "Crop Advisor",
        "fertilizer": "Fertilizer Advisor",
        "chat": "AI Agronomy Chatbot",
        "disease": "Crop Disease Detection",
    }
    item["prediction_type_label"] = type_labels.get(prediction_type, prediction_type.title())
    return item


def load_crop_profiles():
    grouped = defaultdict(list)
    with open(CROP_DATASET, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            grouped[row["label"].strip().lower()].append(
                {feature: float(row[feature]) for feature in FEATURES}
            )

    profiles = {}
    for crop, rows in grouped.items():
        profiles[crop] = {
            feature: sum(row[feature] for row in rows) / len(rows)
            for feature in FEATURES
        }
        profiles[crop]["samples"] = len(rows)
    return profiles


def load_feature_ranges():
    ranges = {feature: [math.inf, -math.inf] for feature in FEATURES}
    with open(CROP_DATASET, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            for feature in FEATURES:
                value = float(row[feature])
                ranges[feature][0] = min(ranges[feature][0], value)
                ranges[feature][1] = max(ranges[feature][1], value)
    return {feature: tuple(bounds) for feature, bounds in ranges.items()}


def load_fertilizer_rows():
    rows = []
    with open(FERTILIZER_DATASET, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(
                {
                    "temperature": float(row["Temparature"]),
                    "humidity": float(row["Humidity "]),
                    "moisture": float(row["Moisture"]),
                    "soil": row["Soil Type"].strip(),
                    "crop": row["Crop Type"].strip(),
                    "N": float(row["Nitrogen"]),
                    "K": float(row["Potassium"]),
                    "P": float(row["Phosphorous"]),
                    "fertilizer": row["Fertilizer Name"].strip(),
                }
            )
    return rows


CROP_PROFILES = load_crop_profiles()
FEATURE_RANGES = load_feature_ranges()
FERTILIZER_ROWS = load_fertilizer_rows()


def feature_similarity(value, target, feature):
    low, high = FEATURE_RANGES[feature]
    spread = max(high - low, 1)
    distance = abs(value - target) / spread
    return max(0, 1 - distance)


def crop_recommendations(inputs, limit=5):
    location = inputs.get("location", "Not specified")
    weights = {
        "N": 0.11,
        "P": 0.11,
        "K": 0.11,
        "temperature": 0.16,
        "humidity": 0.16,
        "ph": 0.16,
        "rainfall": 0.19,
    }
    scored = []
    for crop, profile in CROP_PROFILES.items():
        score = sum(
            weights[feature] * feature_similarity(inputs[feature], profile[feature], feature)
            for feature in FEATURES
        )
        fit = round(score * 100, 1)
        limiting = sorted(
            FEATURES,
            key=lambda feature: abs(inputs[feature] - profile[feature])
            / max(FEATURE_RANGES[feature][1] - FEATURE_RANGES[feature][0], 1),
            reverse=True,
        )[:2]
        market_price, market_value = estimate_crop_market_value(crop, location, fit)
        scored.append(
            {
                "crop": title_crop(crop),
                "score": fit,
                "why": (
                    f"Closest match to {title_crop(crop)} profile; watch "
                    f"{', '.join(limiting)}."
                ),
                "location": location,
                "market_price": market_price,
                "market_value": market_value,
                "profile": {k: round(v, 2) for k, v in profile.items() if k != "samples"},
            }
        )
    return sorted(scored, key=lambda item: item["score"], reverse=True)[:limit]


def crop_recommendation_with_ai_and_ml(inputs, limit=5):
    location = inputs.get("location", "Not specified")
    ml_results = None
    if ML_MODELS_AVAILABLE and hasattr(ml_models, "get_crop_recommendation_ml"):
        try:
            ml_results = ml_models.get_crop_recommendation_ml(inputs, limit=limit)
        except Exception:
            ml_results = None

    if not ml_results:
        ml_results = crop_recommendations(inputs, limit=limit)
    else:
        ml_results = [
            {
                **item,
                "location": location,
                "market_price": estimate_crop_market_value(item.get("crop"), location, item.get("score"))[0],
                "market_value": estimate_crop_market_value(item.get("crop"), location, item.get("score"))[1],
            }
            for item in ml_results
        ]

    prompt = f"""
You are an agronomy advisor. Compare these crop options with the supplied field conditions.
Field: N={inputs['N']}, P={inputs['P']}, K={inputs['K']}, temperature={inputs['temperature']} C, humidity={inputs['humidity']}%, pH={inputs['ph']}, rainfall={inputs['rainfall']} mm.
Location: {location}.
Top options: {', '.join(f"{item['crop']} ({item.get('market_price', 'n/a')})" for item in ml_results)}.
Give a concise practical note recommending the best crop and any caution.
""".strip()
    ai_text, provider = ai_completion(prompt, "You are a practical crop advisor for farmers.", max_tokens=220)
    ai_summary = format_chat_message(ai_text) if ai_text else "No AI explanation available."
    return {
        "location": location,
        "ml_results": ml_results,
        "results": ml_results,
        "ai_summary": ai_summary,
        "ai_provider": provider,
        "ml_summary": "Local ML crop matching was used to rank the options and estimate location-aware market value." if ML_MODELS_AVAILABLE else "Local crop matching was used to rank the options and estimate location-aware market value.",
        "summary": f"{ai_summary}",
    }


def format_fertilizer_name(fertilizer):
    name = str(fertilizer or "").strip()
    if not name:
        return "Fertilizer"
    mapping = {
        "Urea": "Urea (46-0-0)",
        "DAP": "DAP (18-46-0)",
        "Organic": "Organic (0-0-0)",
    }
    return mapping.get(name, name)


def fertilizer_recommendation(inputs):
    crop = inputs["crop"].lower()
    soil = inputs["soil"].lower()
    candidates = []
    for row in FERTILIZER_ROWS:
        score = 0
        score += 25 if row["soil"].lower() == soil else 0
        score += 25 if row["crop"].lower() == crop else 0
        score += max(0, 15 - abs(inputs["temperature"] - row["temperature"]) * 0.7)
        score += max(0, 15 - abs(inputs["humidity"] - row["humidity"]) * 0.35)
        score += max(0, 10 - abs(inputs["moisture"] - row["moisture"]) * 0.35)
        score += max(0, 10 - abs(inputs["N"] - row["N"]) * 0.25)
        score += max(0, 10 - abs(inputs["P"] - row["P"]) * 0.25)
        score += max(0, 10 - abs(inputs["K"] - row["K"]) * 0.25)
        candidates.append((score, row))

    top_pairs = sorted(candidates, key=lambda item: item[0], reverse=True)[:7]
    top_rows = [row for _, row in top_pairs]
    fertilizer = Counter(row["fertilizer"] for row in top_rows).most_common(1)[0][0]
    guide = FERTILIZER_GUIDE.get(fertilizer, FERTILIZER_GUIDE["Organic"])

    crop_aliases = {"paddy": "rice", "maize": "maize", "ground nuts": "mothbeans", "pulses": "pigeonpeas"}
    matched_crop = crop_aliases.get(crop, crop)
    matched_crop = matched_crop if matched_crop in CROP_PROFILES else "rice"
    crop_profile = CROP_PROFILES.get(matched_crop, CROP_PROFILES["rice"])
    gaps = {
        "Nitrogen": round(crop_profile["N"] - inputs["N"], 1),
        "Phosphorus": round(crop_profile["P"] - inputs["P"], 1),
        "Potassium": round(crop_profile["K"] - inputs["K"], 1),
    }
    limiting = [name for name, gap in gaps.items() if gap > 8]
    if not limiting:
        limiting = ["maintenance nutrition"]

    confidence = round(min(96, max(58, sum(score for score, _ in top_pairs) / max(len(top_pairs), 1))), 1)
    formatted_fertilizer = format_fertilizer_name(fertilizer)
    return {
        "fertilizer": fertilizer,
        "fertilizer_display": formatted_fertilizer,
        "confidence": confidence,
        "focus": guide["focus"],
        "timing": guide["timing"],
        "nutrient_gaps": gaps,
        "summary": (
            f"{formatted_fertilizer} is recommended for {title_crop(inputs['crop'])} on "
            f"{inputs['soil']} soil, mainly for {', '.join(limiting)}."
        ),
    }


def fertilizer_recommendation_with_ml(inputs):
    model_predictions = None
    if 'ml_models' in globals() and hasattr(ml_models, 'get_fertilizer_recommendation_models'):
        try:
            model_predictions = ml_models.get_fertilizer_recommendation_models(inputs)
        except Exception:
            model_predictions = None

    if model_predictions:
        fertilizer = model_predictions.get('ensemble', model_predictions.get('random_forest', model_predictions.get('decision_tree', 'Urea')))
        fertilizer = str(fertilizer)
        guide = FERTILIZER_GUIDE.get(fertilizer, FERTILIZER_GUIDE['Organic'])
        formatted_predictions = {key: format_fertilizer_name(value) for key, value in model_predictions.items() if isinstance(value, str)}
        return {
            'fertilizer': fertilizer,
            'fertilizer_display': format_fertilizer_name(fertilizer),
            'confidence': 78.0,
            'focus': guide['focus'],
            'timing': guide['timing'],
            'nutrient_gaps': {},
            'summary': f"{format_fertilizer_name(fertilizer)} predicted by local ML models",
            'model_predictions': model_predictions,
            'model_predictions_display': formatted_predictions,
        }

    if 'ml_models' in globals() and hasattr(ml_models, 'get_fertilizer_recommendation_ml'):
        try:
            num_feats = [
                inputs['temperature'],
                inputs['humidity'],
                inputs['moisture'],
                inputs['N'],
                inputs['P'],
                inputs['K'],
            ]
            soil_val = inputs.get('soil', '')
            crop_val = inputs.get('crop', '')
            try:
                soil_index = next(i for i, s in enumerate(SOIL_TYPES) if s.lower() == str(soil_val).lower())
            except StopIteration:
                soil_index = 0
            try:
                crop_index = next(i for i, c in enumerate(CROP_TYPES) if c.lower() == str(crop_val).lower())
            except StopIteration:
                crop_index = 0
            cat_feats = [soil_index, crop_index]
            pred = ml_models.get_fertilizer_recommendation_ml(num_feats, cat_feats)
            fertilizer = ml_models._fertilizer_label_from_index(pred) if hasattr(ml_models, '_fertilizer_label_from_index') else str(pred)
            guide = FERTILIZER_GUIDE.get(fertilizer, FERTILIZER_GUIDE['Organic'])
            return {
                'fertilizer': fertilizer,
                'fertilizer_display': format_fertilizer_name(fertilizer),
                'confidence': 78.0,
                'focus': guide['focus'],
                'timing': guide['timing'],
                'nutrient_gaps': {},
                'summary': f"{format_fertilizer_name(fertilizer)} predicted by local ML model",
            }
        except Exception:
            pass

    return fertilizer_recommendation(inputs)


def fertilizer_recommendation_with_ai_and_ml(inputs):
    ml_plan = fertilizer_recommendation_with_ml(inputs)
    prompt = f"""
You are an agronomy advisor. Compare the ML fertilizer recommendation with the field data.
Crop: {inputs['crop']}
Soil: {inputs['soil']}
Temperature: {inputs['temperature']} C
Humidity: {inputs['humidity']}%
Moisture: {inputs['moisture']}%
N/P/K: {inputs['N']}/{inputs['P']}/{inputs['K']}
ML recommendation: {format_fertilizer_name(ml_plan.get('fertilizer', 'Fertilizer'))} with focus {ml_plan.get('focus')}.
Give a concise practical note explaining how to apply it and any caution.
""".strip()
    ai_text, provider = ai_completion(prompt, "You are a practical fertilizer advisor for farmers.", max_tokens=220)
    combined = dict(ml_plan)
    ai_summary = format_chat_message(ai_text) if ai_text else "No AI explanation available."
    advisor_summary = (
        f"{format_fertilizer_name(ml_plan.get('fertilizer', 'Fertilizer'))} is recommended with {ml_plan.get('focus', 'a practical focus')} "
        f"and timing of {ml_plan.get('timing', 'the current growth stage')}."
    )
    combined.update(
        {
            "advisor_summary": advisor_summary,
            "fertilizer_display": format_fertilizer_name(ml_plan.get("fertilizer", "")),
            "model_predictions_display": {
                key: format_fertilizer_name(value) for key, value in (ml_plan.get("model_predictions") or {}).items() if isinstance(value, str)
            },
            "ai_summary": ai_summary,
            "ai_provider": provider,
            "ml_summary": ml_plan.get("summary", ""),
            "summary": f"{advisor_summary}\n\nAI note: {ai_summary}",
        }
    )
    return combined


def suitability_for_crop(crop, inputs):
    profile = CROP_PROFILES.get(crop.lower())
    if not profile:
        return 0.72
    scores = [feature_similarity(inputs[feature], profile[feature], feature) for feature in FEATURES]
    return sum(scores) / len(scores)


def location_multiplier_for_text(location):
    location_text = str(location or "").strip().lower()
    if not location_text:
        return 1.0
    if any(term in location_text for term in ["punjab", "haryana", "delhi"]):
        return 1.08
    if any(term in location_text for term in ["gujarat", "maharashtra", "karnataka", "tamil nadu"]):
        return 1.03
    if any(term in location_text for term in ["uttar pradesh", "bihar", "west bengal"]):
        return 0.96
    return 1.0


def estimate_crop_market_value(crop, location=None, fit_score=None):
    crop_key = str(crop or "").strip().lower()
    crop_price_per_ton = CROP_MARKET_PRICE_PER_TON.get(crop_key, 45000)
    base_yield = BASE_YIELD_T_HA.get(crop_key, 3.5)
    fit_multiplier = 1.0
    if fit_score is not None:
        fit_multiplier = 0.6 + max(0.0, min(float(fit_score), 100.0)) / 200.0
    market_value = base_yield * crop_price_per_ton * location_multiplier_for_text(location) * fit_multiplier
    return f"₹{market_value:,.0f}/ha", round(market_value, 2)


def local_yield_plan(inputs):
    crop_key = inputs["crop"].lower()
    base_yield = BASE_YIELD_T_HA.get(crop_key, 3.5)
    suitability = suitability_for_crop(crop_key, inputs)
    ph_penalty = 1 - min(abs(inputs["ph"] - 6.6) * 0.055, 0.22)
    moisture_factor = 1 + min(max((inputs["moisture"] - 45) / 180, -0.12), 0.12)
    fertilizer_factor = 1 + min(inputs["amount"] / 900, 0.18)
    estimate = base_yield * (0.68 + suitability * 0.45) * ph_penalty * moisture_factor * fertilizer_factor
    low = max(0.1, estimate * 0.88)
    high = estimate * 1.12

    confidence = round(max(52, min(94, 62 + suitability * 31 - abs(inputs["ph"] - 6.6) * 3)), 1)
    risk_level = "Low"
    if confidence < 68 or inputs["rainfall"] < 45 or inputs["ph"] < 5.4 or inputs["ph"] > 8.2:
        risk_level = "High"
    elif confidence < 78 or inputs["moisture"] < 25:
        risk_level = "Medium"

    market_value = round(estimate * CROP_MARKET_PRICE_PER_TON.get(crop_key, 45000) * location_multiplier_for_text(inputs.get("location")), 2)
    market_price = f"₹{market_value:,.0f}/ha"

    actions = []
    if inputs["ph"] < 5.8:
        actions.append("Apply lime in a soil-test-guided dose before the next planting window.")
    elif inputs["ph"] > 7.8:
        actions.append("Use acidifying organic matter or sulfur amendments after local soil testing.")
    if inputs["N"] < 45:
        actions.append("Prioritize split nitrogen feeding to reduce leaching losses.")
    if inputs["P"] < 30:
        actions.append("Place phosphorus close to seed/root zones for early vigor.")
    if inputs["K"] < 30:
        actions.append("Add potassium support to improve stress tolerance and grain or fruit fill.")
    if inputs["rainfall"] < 80:
        actions.append("Plan supplemental irrigation around flowering and yield formation.")
    if not actions:
        actions.append("Maintain current nutrient balance and monitor pests after canopy closure.")

    return {
        "yield_range": f"{low:.2f} - {high:.2f} t/ha",
        "estimate": round(estimate, 2),
        "market_price": market_price,
        "confidence": confidence,
        "risk_level": risk_level,
        "summary": (
            f"{title_crop(inputs['crop'])} is projected at {low:.2f} - {high:.2f} t/ha "
            f"with {confidence}% confidence under the submitted field conditions. "
            f"Estimated market return for the field is {market_price}."
        ),
        "actions": actions,
    }


def groq_completion(messages, temperature=0.35, max_tokens=700):
    if not GROQ_API_KEY:
        raise RuntimeError("Groq API key is not configured.")
    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": GROQ_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=25,
    )
    response.raise_for_status()
    payload = response.json()
    return payload["choices"][0]["message"]["content"].strip()


def ai_completion(prompt, system_prompt=None, max_tokens=700):
    if GEMINI_MODEL:
        try:
            gemini_prompt = prompt if not system_prompt else f"{system_prompt}\n\n{prompt}"
            response = GEMINI_MODEL.generate_content(gemini_prompt)
            return response.text.strip(), "Gemini"
        except Exception as exc:
            GEMINI_INIT_ERROR = str(exc)
            pass

    if GROQ_API_KEY:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        try:
            return groq_completion(messages, max_tokens=max_tokens), "Groq"
        except Exception as exc:
            return f"AI enrichment is unavailable. Local scoring was used. Reason: {exc}", "Local"

    if GEMINI_INIT_ERROR:
        return f"Gemini is not configured correctly. Local agronomic scoring was used. Reason: {GEMINI_INIT_ERROR}", "Local"

    return "AI enrichment is not configured; local agronomic scoring was used.", "Local"


def ai_enrichment(inputs, local_plan, fertilizer_plan):
    # Simple caching to avoid repeated external AI calls for identical inputs.
    try:
        AI_CACHE_TTL
    except NameError:
        AI_CACHE_TTL = 60 * 60 * 24  # 24 hours
    global _ai_cache
    if "_ai_cache" not in globals():
        _ai_cache = {}

    # Build a stable fingerprint from inputs, local_plan, and fertilizer_plan
    fingerprint_data = {
        "inputs": inputs,
        "local_plan": {k: local_plan.get(k) for k in ("yield_range", "estimate", "confidence", "risk_level")},
        "fertilizer": {k: fertilizer_plan.get(k) for k in ("fertilizer", "focus")},
    }
    fingerprint = hashlib.sha256(json.dumps(fingerprint_data, sort_keys=True).encode("utf-8")).hexdigest()
    now = time.time()
    cached = _ai_cache.get(fingerprint)
    # Check DB-backed cache first (durable across restarts)
    try:
        row = db_get_ai_cache(fingerprint)
        if row and now - float(row.get("cached_at", 0)) < AI_CACHE_TTL:
            # update in-memory cache for quick future lookups
            _ai_cache[fingerprint] = (float(row.get("cached_at", now)), row.get("result_text", ""))
            return row.get("result_text", "")
    except Exception:
        pass

    if cached and now - cached[0] < AI_CACHE_TTL:
        return cached[1]

    prompt = f"""
Act as an agronomy advisor. Review this field plan and respond in 5 concise bullets.
Crop: {inputs['crop']}
Soil: {inputs['soil']}
Location: {inputs.get('location', 'Not specified')}
NPK: {inputs['N']}/{inputs['P']}/{inputs['K']}
pH: {inputs['ph']}
Weather: {inputs['temperature']} C, {inputs['humidity']}% humidity, {inputs['rainfall']} mm rainfall
Moisture: {inputs['moisture']}%
Fertilizer: {inputs['fertilizer']} at {inputs['amount']} kg/ha
Local estimate: {local_plan['yield_range']}, risk {local_plan['risk_level']}
Estimated market value: {local_plan['market_price']}
Fertilizer recommendation: {fertilizer_plan['fertilizer']} for {fertilizer_plan['focus']}
Give practical actions and caution where uncertainty is high.
""".strip()
    text, provider = ai_completion(
        prompt,
        "You are a precise agricultural decision assistant. Be practical and avoid unsupported guarantees.",
    )
    result_text = f"Provider: {provider}\n\n{text}"
    _ai_cache[fingerprint] = (now, result_text)
    # Persist to DB (durable) and disk (best-effort)
    try:
        db_set_ai_cache(fingerprint, provider, result_text, ts=now)
    except Exception:
        pass
    try:
        with open(AI_CACHE_FILE, "w", encoding="utf-8") as _f:
            json.dump({k: {"ts": v[0], "text": v[1]} for k, v in _ai_cache.items()}, _f)
    except Exception:
        pass
    return result_text


def _background_ai_update(prediction_id, inputs, local_plan, fertilizer_plan, provider_choice):
    """Run AI enrichment in a background thread and update the prediction row when done."""
    try:
        ai_text = ai_enrichment(inputs, local_plan, fertilizer_plan)
    except Exception as exc:
        ai_text = f"AI enrichment failed: {exc}"
    # Append AI text to raw_response (fetch existing raw_response first)
    try:
        with connect_db() as conn:
            row = conn.execute("SELECT raw_response FROM predictions WHERE id = ?", (prediction_id,)).fetchone()
            existing = row["raw_response"] if row and "raw_response" in row.keys() else ""
            new_raw = (existing or "") + "\n\n---\n\n" + ai_text
            conn.execute(
                "UPDATE predictions SET raw_response = ?, ai_enriched = 1, ai_provider = ? WHERE id = ?",
                (new_raw, provider_choice, prediction_id),
            )
            conn.commit()
    except Exception:
        pass


def local_chatbot_response(user_id, message):
    context = build_chat_context(user_id)
    lowered = message.lower()
    tips = []

    if any(word in lowered for word in ["fertil", "urea", "dap", "npk", "nutrient"]):
        tips.append("Focus on matching fertilizer to the crop stage and soil test results rather than using a fixed rate.")
    if any(word in lowered for word in ["yield", "harvest", "production", "output"]):
        tips.append("Yield usually improves most from balanced NPK, stable moisture, and pH close to the crop target.")
    if any(word in lowered for word in ["soil", "ph", "acid", "alkaline"]):
        tips.append("Keep pH near the crop's preferred range; extreme acidity or alkalinity reduces nutrient uptake.")
    if any(word in lowered for word in ["water", "rain", "moisture", "irrig"]):
        tips.append("Water stress is easiest to correct early, especially around flowering and grain or fruit fill.")
    if any(word in lowered for word in ["crop", "plant", "sow", "recommend"]):
        tips.append("Choose the crop with the highest fit score for your soil, rainfall, and temperature window.")

    if not tips:
        tips.append("Share the crop, soil, NPK, pH, rainfall, and moisture values and I can give a practical field plan.")

    if context != "No saved field plans yet.":
        tips.append(f"Latest saved plans: {context}")

    return "\n".join(f"- {tip}" for tip in tips)


def format_chat_message(text):
    cleaned = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    cleaned = re.sub(r"\*\*(.*?)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"^#+\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s*[•*]\s+", "- ", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def strip_chat_boilerplate(text):
    cleaned = str(text or "")
    patterns = [
        r"\n?-\s*Account-Based Farm Management:.*?(?=\n-\s*\w|\Z)",
        r"\n?Account-Based Farm Management:.*?(?=\n\n|\Z)",
        r"\n?-\s*To access your farm's account, please log in to your AgriNexus account\..*?(?=\n-\s*\w|\Z)",
        r"\n?-\s*You can view your saved decisions, track your crop progress, and access other farm management features\..*?(?=\n-\s*\w|\Z)",
    ]
    for pattern in patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def fetch_live_weather(location, api_key=None):
    location_text = str(location or "").strip()
    if not location_text:
        return None

    resolved_api_key = (api_key or OPENWEATHER_API_KEY or "").strip()

    try:
        geo_response = requests.get(
            f"{OPENWEATHER_BASE_URL}/geo/1.0/direct",
            params={"q": location_text, "limit": 1, **({"appid": resolved_api_key} if resolved_api_key else {})},
            timeout=10,
        )
        geo_response.raise_for_status()
        geo_data = geo_response.json() or []
        if not geo_data:
            return None

        location_data = geo_data[0]
        weather_response = requests.get(
            f"{OPENWEATHER_BASE_URL}/data/2.5/weather",
            params={
                "lat": location_data.get("lat"),
                "lon": location_data.get("lon"),
                **({"appid": resolved_api_key} if resolved_api_key else {}),
                "units": "metric",
            },
            timeout=10,
        )
        weather_response.raise_for_status()
        payload = weather_response.json() or {}
        weather_main = (payload.get("weather") or [{}])[0].get("main") or "Clear"
        weather_details = payload.get("main") or {}
        rain_data = payload.get("rain") or {}
        rain_amount = rain_data.get("1h", 0) if isinstance(rain_data, dict) else 0

        return {
            "weather": str(weather_main).strip() or "Clear",
            "temperature": float(weather_details.get("temp", 0)),
            "humidity": float(weather_details.get("humidity", 0)),
            "rainfall": float(rain_amount),
        }
    except Exception:
        return None


def prediction_payload(form):
    crop = form.get("crop", "").strip()
    soil = form.get("soil", "").strip()
    fertilizer = form.get("fertilizer", "").strip()
    if not crop or not soil or not fertilizer:
        raise ValueError("Crop, soil, and fertilizer are required.")

    location = form.get("location", "").strip() or "Not specified"
    weather_value = (form.get("weather") or "").strip()
    temperature_raw = (form.get("temperature") or "").strip()
    humidity_raw = (form.get("humidity") or "").strip()
    rainfall_raw = (form.get("rainfall") or "").strip()
    weather_data = None

    if location != "Not specified" and (not weather_value or not temperature_raw or not humidity_raw or not rainfall_raw):
        weather_data = fetch_live_weather(location)

    if weather_data:
        weather_value = weather_value or weather_data.get("weather", "Field observation")
        temperature_raw = temperature_raw or str(weather_data.get("temperature", ""))
        humidity_raw = humidity_raw or str(weather_data.get("humidity", ""))
        rainfall_raw = rainfall_raw or str(weather_data.get("rainfall", ""))
    else:
        weather_value = weather_value or "Field observation"
        temperature_raw = temperature_raw or "0"
        humidity_raw = humidity_raw or "0"
        rainfall_raw = rainfall_raw or "0"

    inputs = {
        "crop": crop,
        "soil": soil,
        "location": location,
        "weather": weather_value or "Field observation",
        "fertilizer": fertilizer,
        "amount": parse_float(form.get("amount"), "Fertilizer amount", 0, 1000),
        "N": parse_float(form.get("nitrogen"), "Nitrogen", 0, 250),
        "P": parse_float(form.get("phosphorus"), "Phosphorus", 0, 250),
        "K": parse_float(form.get("potassium"), "Potassium", 0, 250),
        "ph": parse_float(form.get("ph"), "Soil pH", 3, 10),
        "temperature": parse_float(temperature_raw, "Temperature", -5, 60),
        "humidity": parse_float(humidity_raw, "Humidity", 0, 100),
        "rainfall": parse_float(rainfall_raw, "Rainfall", 0, 500),
        "moisture": parse_float(form.get("moisture"), "Moisture", 0, 100),
        "satellite_ndvi": parse_optional_float(form.get("satellite_ndvi")),
        "satellite_evi": parse_optional_float(form.get("satellite_evi")),
        "satellite_surface_temp": parse_optional_float(form.get("satellite_surface_temp")),
        "satellite_precipitation": parse_optional_float(form.get("satellite_precipitation")),
    }

    sensor_values = {
        "sensor_id": form.get("sensor_id", "").strip(),
        "sensor_location": form.get("sensor_location", "").strip(),
        "sensor_timestamp": form.get("sensor_timestamp", "").strip(),
        "sensor_temperature": form.get("sensor_temperature", "").strip(),
        "sensor_humidity": form.get("sensor_humidity", "").strip(),
        "sensor_rainfall": form.get("sensor_rainfall", "").strip(),
        "sensor_moisture": form.get("sensor_moisture", "").strip(),
    }
    inputs = apply_sensor_overrides(inputs, sensor_values)

    satellite_values = {
        "satellite_ndvi": form.get("satellite_ndvi", "").strip(),
        "satellite_evi": form.get("satellite_evi", "").strip(),
        "satellite_surface_temp": form.get("satellite_surface_temp", "").strip(),
        "satellite_precipitation": form.get("satellite_precipitation", "").strip(),
    }
    return apply_satellite_overrides(inputs, satellite_values)


def store_prediction(
    inputs,
    local_plan,
    fertilizer_plan,
    crop_plan,
    raw_response,
    user_id,
    prediction_type="yield",
    description=None,
    predicted_yield=None,
    risk_level=None,
    confidence=None,
):
    local_plan = local_plan or {}
    fertilizer_plan = fertilizer_plan or {}
    crop_plan = crop_plan or []
    recommendation = {
        "yield": local_plan,
        "fertilizer": fertilizer_plan,
        "crop_matches": crop_plan,
    }
    sensor_metadata = {}
    for key in ("sensor_id", "sensor_timestamp", "sensor_location"):
        if inputs.get(key):
            sensor_metadata[key] = inputs.get(key)
    sensor_measurements = {}
    for key in ("sensor_temperature", "sensor_humidity", "sensor_rainfall", "sensor_moisture"):
        if inputs.get(key) is not None:
            sensor_measurements[key] = inputs.get(key)
    if sensor_metadata or sensor_measurements:
        recommendation["sensor_data"] = {**sensor_metadata, **sensor_measurements}

    resolved_prediction_type = str(prediction_type or "yield").strip() or "yield"
    resolved_description = description or "AgriNexus hybrid agronomic score"
    resolved_predicted_yield = str(
        predicted_yield
        if predicted_yield is not None
        else local_plan.get("yield_range") or raw_response or "No result"
    )
    resolved_risk_level = risk_level if risk_level is not None else local_plan.get("risk_level") or "Unrated"
    resolved_confidence = confidence if confidence is not None else local_plan.get("confidence")
    with connect_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO predictions (
                soil, weather, fertilizer, amount, crop, predicted_yield, description,
                raw_response, prediction_type, location, market_price, nitrogen,
                phosphorus, potassium, ph, temperature, humidity, rainfall, moisture,
                risk_level, confidence, recommendation, created_at, user_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                inputs.get("soil", "Not specified"),
                inputs.get("weather", "Field observation"),
                inputs.get("fertilizer", "Not specified"),
                inputs.get("amount", 0),
                inputs.get("crop", "Not specified"),
                resolved_predicted_yield,
                resolved_description,
                raw_response,
                resolved_prediction_type,
                inputs.get("location", "Not specified"),
                local_plan.get("market_price", "₹0/ha"),
                inputs.get("N"),
                inputs.get("P"),
                inputs.get("K"),
                inputs.get("ph"),
                inputs.get("temperature"),
                inputs.get("humidity"),
                inputs.get("rainfall"),
                inputs.get("moisture"),
                resolved_risk_level,
                resolved_confidence,
                json.dumps(recommendation),
                datetime.utcnow().isoformat(timespec="seconds"),
                user_id,
            ),
        )
        conn.commit()
        return cursor.lastrowid


def get_all_predictions(user_id=None):
    with connect_db() as conn:
        if user_id:
            rows = conn.execute(
                "SELECT * FROM predictions WHERE user_id = ? ORDER BY id DESC",
                (user_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM predictions WHERE user_id IS NULL ORDER BY id DESC"
            ).fetchall()
    return [enrich_prediction_row(row) for row in rows]


def get_prediction(prediction_id, user_id=None):
    with connect_db() as conn:
        if user_id:
            row = conn.execute(
                "SELECT * FROM predictions WHERE id = ? AND user_id = ?",
                (prediction_id, user_id),
            ).fetchone()
        else:
            row = conn.execute("SELECT * FROM predictions WHERE id = ?", (prediction_id,)).fetchone()
    if not row:
        return None
    item = enrich_prediction_row(row)
    try:
        item["recommendation_data"] = json.loads(item.get("recommendation") or "{}")
    except json.JSONDecodeError:
        item["recommendation_data"] = {}
    return item


@app.route("/prediction_status/<int:prediction_id>")
@login_required
def prediction_status(prediction_id):
    user = current_user()
    item = get_prediction(prediction_id, user_id=user["id"] if user else None)
    if not item:
        return jsonify(success=False, error="Not found"), 404
    return jsonify(
        success=True,
        id=item.get("id"),
        ai_enriched=1 if item.get("ai_enriched") else 0,
        ai_provider=item.get("ai_provider"),
        raw_response=item.get("raw_response", ""),
    )


def dashboard_metrics(user_id=None):
    # Simple in-memory TTL cache to avoid repeated DB hits for dashboard metrics.
    # Cache keyed by user_id; cache entries expire after CACHE_TTL seconds.
    global _metrics_cache
    try:
        CACHE_TTL
    except NameError:
        CACHE_TTL = 30  # seconds
    if "_metrics_cache" not in globals():
        _metrics_cache = {}

    now = time.time()
    cached = _metrics_cache.get(user_id)
    if cached and now - cached[0] < CACHE_TTL:
        return cached[1]

    predictions = get_all_predictions(user_id)
    crop_counts = Counter(item.get("crop") for item in predictions if item.get("crop"))
    risk_counts = Counter(item.get("risk_level") or "Unrated" for item in predictions)
    avg_confidence = 0
    confidences = [item["confidence"] for item in predictions if item.get("confidence") is not None]
    if confidences:
        avg_confidence = round(sum(confidences) / len(confidences), 1)
    result = {
        "total": len(predictions),
        "top_crop": crop_counts.most_common(1)[0][0] if crop_counts else "No records",
        "avg_confidence": avg_confidence,
        "risk_counts": dict(risk_counts),
        "recent": predictions[:5],
    }
    _metrics_cache[user_id] = (now, result)
    return result


def chat_history(user_id, limit=20):
    with connect_db() as conn:
        rows = conn.execute(
            """
            SELECT * FROM chat_messages
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
    history = []
    for row in reversed(rows):
        item = dict(row)
        item["display_message"] = format_chat_message(item.get("message"))
        history.append(item)
    return history


def save_chat_message(user_id, role, message, provider=None):
    with connect_db() as conn:
        conn.execute(
            """
            INSERT INTO chat_messages (user_id, role, message, provider, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, role, message, provider, datetime.utcnow().isoformat(timespec="seconds")),
        )
        conn.commit()


def build_chat_context(user_id):
    recent = get_all_predictions(user_id)[:3]
    if not recent:
        return "No saved field plans yet."
    lines = []
    for item in recent:
        lines.append(
            f"{item['crop']} on {item['soil']} soil: yield {item['predicted_yield']}, "
            f"risk {item.get('risk_level')}, fertilizer {item['fertilizer']}."
        )
    return "\n".join(lines)


def chatbot_reply(user_id, message):
    history = chat_history(user_id, limit=8)
    system_prompt = (
        f"You are {APP_NAME}'s farm operations chatbot. Use only current project capabilities: "
        "yield planning, crop recommendation, fertilizer strategy, and saved field context. "
        "Do not mention login, account management, CSV export, or product help text unless the user explicitly asks. "
        "Give concise, practical agronomy guidance and avoid claiming certainty where soil tests or local extension advice are needed."
    )
    context = build_chat_context(user_id)
    transcript = "\n".join(
        f"{item['role']}: {item['message']}" for item in history[-6:] if item["role"] in {"user", "assistant"}
    )
    prompt = f"""
Recent saved field context:
{context}

Recent conversation:
{transcript or "No previous messages."}

Farmer question:
{message}
""".strip()
    text, provider = ai_completion(prompt, system_prompt, max_tokens=650)
    if not text or not str(text).strip():
        text = local_chatbot_response(user_id, message)
        provider = "Local"
    elif provider == "Local":
        text = local_chatbot_response(user_id, message)
    text = strip_chat_boilerplate(text)
    return format_chat_message(text), provider


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        farm_name = request.form.get("farm_name", "").strip()
        location = request.form.get("location", "").strip()
        if not name or not email or len(password) < 6:
            return render_template(
                "auth.html",
                app_name=APP_NAME,
                mode="register",
                error="Name, email, and a 6+ character password are required.",
            )
        try:
            with connect_db() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO users (name, email, password_hash, farm_name, location, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        name,
                        email,
                        generate_password_hash(password),
                        farm_name,
                        location,
                        datetime.utcnow().isoformat(timespec="seconds"),
                    ),
                )
                conn.commit()
                session["user_id"] = cursor.lastrowid
            return redirect(url_for("index"))
        except sqlite3.IntegrityError:
            return render_template(
                "auth.html",
                app_name=APP_NAME,
                mode="register",
                error="An account already exists for that email.",
            )
    return render_template("auth.html", app_name=APP_NAME, mode="register")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        with connect_db() as conn:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if row and check_password_hash(row["password_hash"], password):
            session["user_id"] = row["id"]
            return redirect(request.args.get("next") or url_for("index"))
        return render_template(
            "auth.html",
            app_name=APP_NAME,
            mode="login",
            error="Invalid email or password.",
        )
    return render_template("auth.html", app_name=APP_NAME, mode="login")


@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        if not email:
            return render_template(
                "auth.html",
                app_name=APP_NAME,
                mode="forgot_password",
                error="Please enter your email address.",
            )

        with connect_db() as conn:
            user = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            if not user:
                return render_template(
                    "auth.html",
                    app_name=APP_NAME,
                    mode="forgot_password",
                    error="We could not find an account for that email.",
                )

            conn.execute("DELETE FROM password_reset_otps WHERE email = ?", (email,))
            otp = f"{secrets.randbelow(900000) + 100000:06d}"
            otp_hash = generate_password_hash(otp)
            now = datetime.utcnow()
            conn.execute(
                """
                INSERT INTO password_reset_otps (email, otp_hash, created_at, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                (email, otp_hash, now.isoformat(timespec="seconds"), (now + timedelta(minutes=10)).isoformat(timespec="seconds")),
            )
            conn.commit()

        sent = send_password_reset_email(email, otp)
        if sent:
            success_message = "OTP sent to your email. Check your inbox and enter the code below."
        else:
            success_message = "OTP generated. Use the code below to reset your password."

        return render_template(
            "auth.html",
            app_name=APP_NAME,
            mode="reset_password",
            success=success_message,
            otp=otp,
            email=email,
        )

    return render_template("auth.html", app_name=APP_NAME, mode="forgot_password")


@app.route("/reset_password", methods=["GET", "POST"])
def reset_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        otp = request.form.get("otp", "").strip()
        new_password = request.form.get("new_password", "")

        if not email or not otp or len(new_password) < 6:
            return render_template(
                "auth.html",
                app_name=APP_NAME,
                mode="reset_password",
                error="Enter your email, the 6-digit OTP, and a new password with at least 6 characters.",
                email=email,
            )

        with connect_db() as conn:
            row = conn.execute(
                "SELECT * FROM password_reset_otps WHERE email = ? ORDER BY created_at DESC LIMIT 1",
                (email,),
            ).fetchone()
            if not row:
                return render_template(
                    "auth.html",
                    app_name=APP_NAME,
                    mode="reset_password",
                    error="No OTP was found for that email. Request a new code.",
                    email=email,
                )

            expires_at = datetime.fromisoformat(row["expires_at"])
            if datetime.utcnow() > expires_at:
                return render_template(
                    "auth.html",
                    app_name=APP_NAME,
                    mode="reset_password",
                    error="The OTP has expired. Request a new one.",
                    email=email,
                )

            if not check_password_hash(row["otp_hash"], otp):
                return render_template(
                    "auth.html",
                    app_name=APP_NAME,
                    mode="reset_password",
                    error="The OTP is incorrect.",
                    email=email,
                )

            conn.execute(
                "UPDATE users SET password_hash = ? WHERE email = ?",
                (generate_password_hash(new_password), email),
            )
            conn.execute("DELETE FROM password_reset_otps WHERE email = ?", (email,))
            conn.commit()

        return render_template(
            "auth.html",
            app_name=APP_NAME,
            mode="login",
            success="Password updated. Please sign in with your new password.",
        )

    return render_template("auth.html", app_name=APP_NAME, mode="reset_password")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/account")
@app.route("/dashboard")
@login_required
def account():
    user_id = ensure_active_user_id()
    user = current_user()
    metrics = dashboard_metrics(user_id)
    with connect_db() as conn:
        chat_count = conn.execute(
            "SELECT COUNT(*) AS total FROM chat_messages WHERE user_id = ?",
            (user_id,),
        ).fetchone()["total"]
    return render_template(
        "account.html",
        app_name=APP_NAME,
        user=user,
        metrics=metrics,
        chat_count=chat_count,
    )


@app.route("/")
def index():
    user = current_user()
    return render_template(
        "index.html",
        app_name=APP_NAME,
        crops=list(reversed(list(CROP_TYPES))),
        soils=list(reversed(list(SOIL_TYPES))),
        fertilizers=sorted(FERTILIZER_GUIDE, reverse=True),
        metrics=dashboard_metrics(user["id"] if user else None),
        gemini_enabled=bool(GEMINI_MODEL),
        groq_enabled=bool(GROQ_API_KEY),
        initial_values={
            "crop": request.args.get("crop", ""),
            "soil": request.args.get("soil", ""),
            "fertilizer": request.args.get("fertilizer", ""),
            "amount": request.args.get("amount", ""),
            "weather": request.args.get("weather", ""),
            "location": request.args.get("location", ""),
            "nitrogen": request.args.get("nitrogen", ""),
            "phosphorus": request.args.get("phosphorus", ""),
            "potassium": request.args.get("potassium", ""),
            "ph": request.args.get("ph", ""),
            "temperature": request.args.get("temperature", ""),
            "humidity": request.args.get("humidity", ""),
            "rainfall": request.args.get("rainfall", ""),
            "moisture": request.args.get("moisture", ""),
            "provider": request.args.get("provider", "local"),
        },
    )


@app.route("/predict", methods=["GET", "POST"])
def predict():
    if request.method == "GET":
        return redirect(url_for("index"))
    try:
        was_guest = not session.get("user_id")
        inputs = prediction_payload(request.form)
        # Always compute local plan and recommendations (fast, deterministic)
        local_plan = local_yield_plan(inputs)
        fertilizer_plan = fertilizer_recommendation_with_ml(inputs)
        crop_plan = crop_recommendations(inputs, limit=3)

        # Determine whether to call AI enrichment
        provider_choice = (request.form.get("provider") or "local").strip().lower()
        raw_response = f"Provider: Local\n\n{local_plan.get('summary', '')}\n\n{fertilizer_plan.get('summary', '')}"
        # If the user asked for AI-only, run synchronously; if hybrid, return fast and enrich in background
        if provider_choice == "ai":
            try:
                ai_text = ai_enrichment(inputs, local_plan, fertilizer_plan)
            except Exception as exc:
                ai_text = f"AI enrichment failed: {exc}"
            raw_response += f"\n\n---\n\n{ai_text}"
        user_id = ensure_active_user_id()
        prediction_id = store_prediction(
            inputs,
            local_plan,
            fertilizer_plan,
            crop_plan,
            raw_response,
            user_id,
        )
        # If hybrid provider was requested, enrich in background to keep UX fast
        if provider_choice == "hybrid":
            try:
                thread = threading.Thread(
                    target=_background_ai_update,
                    args=(prediction_id, inputs, local_plan, fertilizer_plan, provider_choice),
                    daemon=True,
                )
                thread.start()
            except Exception:
                pass
        session["result_id"] = prediction_id

        if was_guest:
            user_id = ensure_active_user_id()
            return render_template(
                "index.html",
                app_name=APP_NAME,
                crops=list(reversed(list(CROP_TYPES))),
                soils=list(reversed(list(SOIL_TYPES))),
                fertilizers=sorted(FERTILIZER_GUIDE, reverse=True),
                metrics=dashboard_metrics(user_id),
                gemini_enabled=bool(GEMINI_MODEL),
                groq_enabled=bool(GROQ_API_KEY),
                initial_values={
                    "crop": request.form.get("crop", ""),
                    "soil": request.form.get("soil", ""),
                    "fertilizer": request.form.get("fertilizer", ""),
                    "amount": request.form.get("amount", ""),
                    "weather": request.form.get("weather", ""),
                    "location": request.form.get("location", ""),
                    "nitrogen": request.form.get("nitrogen", ""),
                    "phosphorus": request.form.get("phosphorus", ""),
                    "potassium": request.form.get("potassium", ""),
                    "ph": request.form.get("ph", ""),
                    "temperature": request.form.get("temperature", ""),
                    "humidity": request.form.get("humidity", ""),
                    "rainfall": request.form.get("rainfall", ""),
                    "moisture": request.form.get("moisture", ""),
                    "satellite_ndvi": request.form.get("satellite_ndvi", ""),
                    "satellite_evi": request.form.get("satellite_evi", ""),
                    "satellite_surface_temp": request.form.get("satellite_surface_temp", ""),
                    "satellite_precipitation": request.form.get("satellite_precipitation", ""),
                    "provider": request.form.get("provider", "local"),
                },
            )

        return redirect(url_for("prediction_detail", prediction_id=prediction_id))
    except ValueError as exc:
        return render_template(
            "index.html",
            app_name=APP_NAME,
            crops=CROP_TYPES,
            soils=SOIL_TYPES,
            fertilizers=sorted(FERTILIZER_GUIDE),
            metrics=dashboard_metrics(session.get("user_id")),
            gemini_enabled=bool(GEMINI_MODEL),
            groq_enabled=bool(GROQ_API_KEY),
            error=str(exc),
        )


@app.route("/yield-planner")
def yield_planner():
    return index()


@app.route("/crop-recommendation", methods=["GET", "POST"])
@login_required
def crop_recommendation():
    result = None
    error = None
    if request.method == "POST":
        try:
            inputs = {
                "crop": request.form.get("crop", "rice").strip() or "rice",
                "N": parse_float(request.form.get("nitrogen"), "Nitrogen", 0, 250),
                "P": parse_float(request.form.get("phosphorus"), "Phosphorus", 0, 250),
                "K": parse_float(request.form.get("potassium"), "Potassium", 0, 250),
                "temperature": parse_float(request.form.get("temperature"), "Temperature", -5, 60),
                "humidity": parse_float(request.form.get("humidity"), "Humidity", 0, 100),
                "moisture": parse_float(request.form.get("moisture"), "Moisture", 0, 100),
                "ph": parse_float(request.form.get("ph"), "Soil pH", 3, 10),
                "rainfall": parse_float(request.form.get("rainfall"), "Rainfall", 0, 500),
                "satellite_ndvi": parse_float(request.form.get("satellite_ndvi"), "Satellite NDVI", -1.0, 1.0) if request.form.get("satellite_ndvi") else None,
                "satellite_evi": parse_float(request.form.get("satellite_evi"), "Satellite EVI", -1.0, 1.0) if request.form.get("satellite_evi") else None,
                "satellite_surface_temp": parse_float(request.form.get("satellite_surface_temp"), "Satellite surface temp", -50, 80) if request.form.get("satellite_surface_temp") else None,
                "satellite_precipitation": parse_float(request.form.get("satellite_precipitation"), "Satellite precipitation", 0, 500) if request.form.get("satellite_precipitation") else None,
                "amount": parse_float(request.form.get("amount"), "Fertilizer amount", 0, 1000),
                "location": request.form.get("location", "").strip() or "Not specified",
            }
            result = crop_recommendation_with_ai_and_ml(inputs)
            impact = local_yield_plan(inputs)
            result = {**result, **impact}
            top_result = (result.get("results") or [{}])[0] if isinstance(result, dict) else {}
            store_prediction(
                inputs,
                {
                    "yield_range": impact.get("yield_range", top_result.get("crop", "Crop advisor")),
                    "risk_level": impact.get("risk_level", "Low"),
                    "confidence": impact.get("confidence", round(top_result.get("score", 0), 1)),
                },
                {"fertilizer": "Not specified"},
                result.get("results", []) if isinstance(result, dict) else [],
                result.get("summary") or result.get("ai_summary"),
                ensure_active_user_id(),
                prediction_type="crop",
                description="Crop advisor recommendation with fertilizer impact",
                predicted_yield=impact.get("yield_range", top_result.get("crop", "Crop advisor")),
                risk_level=impact.get("risk_level", "Low"),
                confidence=impact.get("confidence", round(top_result.get("score", 0), 1)),
            )
        except ValueError as exc:
            error = str(exc)
    return render_template("crop_recommend.html", app_name=APP_NAME, result=result, error=error, crops=CROP_TYPES)


@app.route("/fertilizer-recommendation", methods=["GET", "POST"])
@login_required
def fertilizer_recommend():
    result = None
    error = None
    if request.method == "POST":
        try:
            inputs = {
                "temperature": parse_float(request.form.get("temperature"), "Temperature", -5, 60),
                "humidity": parse_float(request.form.get("humidity"), "Humidity", 0, 100),
                "moisture": parse_float(request.form.get("moisture"), "Moisture", 0, 100),
                "N": parse_float(request.form.get("nitrogen"), "Nitrogen", 0, 250),
                "P": parse_float(request.form.get("phosphorus"), "Phosphorus", 0, 250),
                "K": parse_float(request.form.get("potassium"), "Potassium", 0, 250),
                "ph": parse_float(request.form.get("ph"), "Soil pH", 3, 10),
                "rainfall": parse_float(request.form.get("rainfall"), "Rainfall", 0, 500),
                "amount": parse_float(request.form.get("amount"), "Fertilizer amount", 0, 1000),
                "soil": request.form.get("soil", "").strip(),
                "crop": request.form.get("crop", "").strip(),
            }
            if not inputs["soil"] or not inputs["crop"]:
                raise ValueError("Soil and crop are required.")
            result = fertilizer_recommendation_with_ai_and_ml(inputs)
            impact = local_yield_plan(inputs)
            result = {**result, **impact}
            store_prediction(
                inputs,
                {"yield_range": impact.get("yield_range", ""), "risk_level": impact.get("risk_level", "Low"), "confidence": impact.get("confidence", 0)},
                result,
                [],
                result.get("summary") or result.get("advisor_summary"),
                ensure_active_user_id(),
                prediction_type="fertilizer",
                description="Fertilizer advisor recommendation and impact",
                predicted_yield=impact.get("yield_range", ""),
                risk_level=impact.get("risk_level", "Low"),
                confidence=impact.get("confidence", 0),
            )
        except ValueError as exc:
            error = str(exc)
    return render_template(
        "fertilizer_recommend.html",
        app_name=APP_NAME,
        soils=SOIL_TYPES,
        crops=CROP_TYPES,
        result=result,
        error=error,
    )


@app.route("/fertilizer-impact", methods=["GET", "POST"])
@login_required
def fertilizer_impact():
    result = None
    error = None
    initial_values = {
        "crop": CROP_TYPES[0] if CROP_TYPES else "",
        "soil": SOIL_TYPES[0] if SOIL_TYPES else "",
        "temperature": 25,
        "humidity": 55,
        "moisture": 45,
        "nitrogen": 35,
        "phosphorus": 28,
        "potassium": 20,
        "ph": 6.5,
        "rainfall": 120,
        "amount": 100,
    }
    if request.method == "POST":
        try:
            inputs = {
                "temperature": parse_float(request.form.get("temperature"), "Temperature", -5, 60),
                "humidity": parse_float(request.form.get("humidity"), "Humidity", 0, 100),
                "moisture": parse_float(request.form.get("moisture"), "Moisture", 0, 100),
                "N": parse_float(request.form.get("nitrogen"), "Nitrogen", 0, 250),
                "P": parse_float(request.form.get("phosphorus"), "Phosphorus", 0, 250),
                "K": parse_float(request.form.get("potassium"), "Potassium", 0, 250),
                "ph": parse_float(request.form.get("ph"), "Soil pH", 3, 10),
                "rainfall": parse_float(request.form.get("rainfall"), "Rainfall", 0, 500),
                "amount": parse_float(request.form.get("amount"), "Fertilizer amount", 0, 1000),
                "soil": request.form.get("soil", "").strip(),
                "crop": request.form.get("crop", "").strip(),
            }
            if not inputs["soil"] or not inputs["crop"]:
                raise ValueError("Soil and crop are required.")
            result = fertilizer_recommendation_with_ai_and_ml(inputs)
            impact = local_yield_plan(inputs)
            result = {**result, **impact, "inputs": inputs}
            store_prediction(
                inputs,
                {"yield_range": impact.get("yield_range", ""), "risk_level": impact.get("risk_level", "Low"), "confidence": impact.get("confidence", 0)},
                result,
                [],
                result.get("summary") or result.get("advisor_summary"),
                ensure_active_user_id(),
                prediction_type="fertilizer",
                description="Fertilizer impact prediction and summary",
                predicted_yield=impact.get("yield_range", ""),
                risk_level=impact.get("risk_level", "Low"),
                confidence=impact.get("confidence", 0),
            )
            initial_values = {
                "crop": request.form.get("crop", initial_values["crop"]),
                "soil": request.form.get("soil", initial_values["soil"]),
                "temperature": request.form.get("temperature", initial_values["temperature"]),
                "humidity": request.form.get("humidity", initial_values["humidity"]),
                "moisture": request.form.get("moisture", initial_values["moisture"]),
                "nitrogen": request.form.get("nitrogen", initial_values["nitrogen"]),
                "phosphorus": request.form.get("phosphorus", initial_values["phosphorus"]),
                "potassium": request.form.get("potassium", initial_values["potassium"]),
                "ph": request.form.get("ph", initial_values["ph"]),
                "rainfall": request.form.get("rainfall", initial_values["rainfall"]),
                "amount": request.form.get("amount", initial_values["amount"]),
            }
        except ValueError as exc:
            error = str(exc)
    return render_template(
        "fertilizer_impact.html",
        app_name=APP_NAME,
        soils=SOIL_TYPES,
        crops=CROP_TYPES,
        result=result,
        error=error,
        initial_values=initial_values,
    )


@app.route("/prediction")
@login_required
def prediction():
    prediction_id = session.get("result_id")
    if not prediction_id:
        return redirect(url_for("index"))
    return redirect(url_for("prediction_detail", prediction_id=prediction_id))


@app.route("/prediction/<int:prediction_id>")
@login_required
def prediction_detail(prediction_id):
    user_id = ensure_active_user_id()
    prediction_item = get_prediction(prediction_id, user_id)
    if not prediction_item:
        return redirect(url_for("index"))
    return render_template("prediction.html", app_name=APP_NAME, prediction=prediction_item)


@app.route("/all_responses")
@login_required
def all_responses():
    user_id = ensure_active_user_id()
    return render_template(
        "all_responses.html",
        app_name=APP_NAME,
        predictions=get_all_predictions(user_id),
        metrics=dashboard_metrics(user_id),
    )


@app.route("/export/predictions.csv")
@login_required
def export_predictions():
    user_id = ensure_active_user_id()
    rows = get_all_predictions(user_id)
    output = io.StringIO()
    fields = [
        "id",
        "created_at",
        "crop",
        "soil",
        "fertilizer",
        "amount",
        "predicted_yield",
        "risk_level",
        "confidence",
        "nitrogen",
        "phosphorus",
        "potassium",
        "ph",
        "temperature",
        "humidity",
        "rainfall",
        "moisture",
    ]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field) for field in fields})
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=agrinexus_predictions.csv"},
    )


def build_api_inputs(data):
    if not isinstance(data, dict):
        data = {}
    sensor_source = data.get("sensor_data") if isinstance(data.get("sensor_data"), dict) else data
    satellite_source = data.get("satellite_data") if isinstance(data.get("satellite_data"), dict) else data

    inputs = {
        "N": parse_float(data.get("nitrogen"), "Nitrogen", 0, 250),
        "P": parse_float(data.get("phosphorus"), "Phosphorus", 0, 250),
        "K": parse_float(data.get("potassium"), "Potassium", 0, 250),
        "temperature": parse_float(
            sensor_source.get("sensor_temperature") or sensor_source.get("temperature") or data.get("temperature"),
            "Temperature",
            -5,
            60,
        ),
        "humidity": parse_float(
            sensor_source.get("sensor_humidity") or sensor_source.get("humidity") or data.get("humidity"),
            "Humidity",
            0,
            100,
        ),
        "ph": parse_float(data.get("ph"), "Soil pH", 3, 10),
        "rainfall": parse_float(
            sensor_source.get("sensor_rainfall") or sensor_source.get("rainfall") or data.get("rainfall"),
            "Rainfall",
            0,
            500,
        ),
        "moisture": parse_float(
            sensor_source.get("sensor_moisture") or sensor_source.get("moisture") or data.get("moisture"),
            "Moisture",
            0,
            100,
        ),
        "soil": data.get("soil", "Loamy"),
        "crop": data.get("crop", "Rice"),
        "fertilizer": data.get("fertilizer", "Organic"),
        "amount": parse_float(data.get("amount", 80), "Amount", 0, 1000),
        "weather": data.get("weather", "API request"),
        "sensor_id": data.get("sensor_id"),
        "sensor_timestamp": data.get("sensor_timestamp"),
        "sensor_location": data.get("sensor_location"),
        "satellite_ndvi": parse_optional_float(satellite_source.get("satellite_ndvi") or satellite_source.get("ndvi") or data.get("satellite_ndvi") or data.get("ndvi")),
        "satellite_evi": parse_optional_float(satellite_source.get("satellite_evi") or satellite_source.get("evi") or data.get("satellite_evi") or data.get("evi")),
        "satellite_surface_temp": parse_optional_float(satellite_source.get("satellite_surface_temp") or satellite_source.get("surface_temp") or data.get("satellite_surface_temp") or data.get("surface_temp")),
        "satellite_precipitation": parse_optional_float(satellite_source.get("satellite_precipitation") or satellite_source.get("precipitation") or data.get("satellite_precipitation") or data.get("precipitation")),
    }
    inputs = apply_sensor_overrides(inputs, sensor_source)
    return apply_satellite_overrides(inputs, satellite_source)


@app.route("/api/recommendations", methods=["POST"])
def api_recommendations():
    data = request.get_json(silent=True) or {}
    try:
        inputs = build_api_inputs(data)
        return jsonify(
            {
                "inputs": {k: inputs.get(k) for k in ["crop", "soil", "fertilizer", "amount", "weather", "sensor_id", "sensor_timestamp", "sensor_location", "satellite_ndvi", "satellite_evi", "satellite_surface_temp", "satellite_precipitation", "temperature", "humidity", "rainfall", "moisture"]},
                "crop_recommendations": crop_recommendations(inputs),
                "fertilizer_recommendation": fertilizer_recommendation(inputs),
                "yield_plan": local_yield_plan(inputs),
            }
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/iot-sensor", methods=["POST"])
def api_iot_sensor():
    data = request.get_json(silent=True) or {}
    try:
        inputs = build_api_inputs(data)
        return jsonify(
            {
                "sensor_id": data.get("sensor_id"),
                "sensor_timestamp": data.get("sensor_timestamp"),
                "sensor_location": data.get("sensor_location"),
                "sensor_data": {
                    "temperature": inputs.get("temperature"),
                    "humidity": inputs.get("humidity"),
                    "rainfall": inputs.get("rainfall"),
                    "moisture": inputs.get("moisture"),
                },
                "satellite_data": {
                    "ndvi": inputs.get("satellite_ndvi"),
                    "evi": inputs.get("satellite_evi"),
                    "surface_temp": inputs.get("satellite_surface_temp"),
                    "precipitation": inputs.get("satellite_precipitation"),
                },
                "crop_recommendations": crop_recommendations(inputs),
                "fertilizer_recommendation": fertilizer_recommendation(inputs),
                "yield_plan": local_yield_plan(inputs),
            }
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/chat", methods=["GET", "POST"])
@login_required
def chat():
    error = None
    user_id = ensure_active_user_id()
    if request.method == "POST":
        message = request.form.get("message", "").strip()
        if message:
            save_chat_message(user_id, "user", message)
            reply, provider = chatbot_reply(user_id, message)
            save_chat_message(user_id, "assistant", reply, provider)
            store_prediction(
                {
                    "soil": "Chat",
                    "weather": "Conversation",
                    "fertilizer": "Chat",
                    "amount": 0,
                    "crop": "Chat",
                    "location": "Chat",
                    "N": 0,
                    "P": 0,
                    "K": 0,
                    "ph": 0,
                    "temperature": 0,
                    "humidity": 0,
                    "rainfall": 0,
                    "moisture": 0,
                },
                {"yield_range": "Chat session", "risk_level": "Unrated", "confidence": 0},
                {"fertilizer": "Chat"},
                [],
                reply,
                user_id,
                prediction_type="chat",
                description=f"AI agronomy chatbot: {message}",
                predicted_yield="Chat session",
                risk_level="Unrated",
                confidence=0,
            )
        else:
            error = "Type a question before sending."
    return render_template(
        "chat.html",
        app_name=APP_NAME,
        messages=chat_history(user_id),
        error=error,
        gemini_enabled=bool(GEMINI_MODEL),
        groq_enabled=bool(GROQ_API_KEY),
    )


@app.route("/api/chat", methods=["POST"])
def api_chat():
    user_id = ensure_active_user_id()
    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()
    if not message:
        return jsonify({"error": "Message is required."}), 400
    save_chat_message(user_id, "user", message)
    reply, provider = chatbot_reply(user_id, message)
    save_chat_message(user_id, "assistant", reply, provider)
    return jsonify({"reply": reply, "provider": provider})


@app.route("/crop-disease", methods=["GET", "POST"])
@login_required
def crop_disease():
    result = None
    error = None
    image_file = None
    treatment = None
    fertilizer = None
    if request.method == "POST":
        crop = request.form.get("crop", "").strip().lower()
        if not crop:
            error = "Please select a crop type."
        elif "file" not in request.files or not request.files["file"].filename:
            error = "Please upload a leaf image."
        else:
            file = request.files["file"]
            try:
                from werkzeug.utils import secure_filename
                upload_dir = os.path.join(app.root_path, "uploads")
                os.makedirs(upload_dir, exist_ok=True)
                filename = secure_filename(file.filename)
                file_path = os.path.join(upload_dir, filename)
                file.save(file_path)
                prediction_index = ml_models.img_predict(file_path, crop)
                disease_details = ml_models.get_disease_details(crop, prediction_index)
                result = disease_details["disease"]
                treatment = disease_details["treatment"]
                fertilizer = disease_details["fertilizer"]
                image_file = filename
                store_prediction(
                    {
                        "soil": "Disease detection",
                        "weather": "Image analysis",
                        "fertilizer": fertilizer or "Not specified",
                        "amount": 0,
                        "crop": crop.title(),
                        "location": "Image upload",
                        "N": 0,
                        "P": 0,
                        "K": 0,
                        "ph": 0,
                        "temperature": 0,
                        "humidity": 0,
                        "rainfall": 0,
                        "moisture": 0,
                    },
                    {"yield_range": result, "risk_level": "Medium", "confidence": 0},
                    {"fertilizer": fertilizer or "Not specified"},
                    [{"crop": crop.title(), "score": 0.9}],
                    result,
                    ensure_active_user_id(),
                    prediction_type="disease",
                    description=f"Crop disease detection for {crop.title()}",
                    predicted_yield=result,
                    risk_level="Medium",
                    confidence=0,
                )
            except FileNotFoundError as exc:
                error = f"No disease model available for '{crop}'. Supported crops: {', '.join(ml_models.CROP_DISEASE_LIST)}"
            except Exception as exc:
                error = f"Prediction error: {exc}"
    return render_template(
        "crop_disease.html",
        app_name=APP_NAME,
        crops=ml_models.CROP_DISEASE_LIST,
        result=result,
        treatment=treatment,
        fertilizer=fertilizer,
        image_file=image_file,
        error=error,
    )


@app.route("/uploads/<filename>")
def uploaded_file(filename):
    from flask import send_from_directory
    upload_dir = os.path.join(BASE_DIR, "uploads")
    return send_from_directory(upload_dir, filename)


@app.route("/about")
def about():
    return render_template("about.html", app_name=APP_NAME)


@app.route("/developer")
def developer():
    return render_template("developer.html", app_name=APP_NAME)


init_db()

if __name__ == "__main__":
    app.run(debug=True)
