import json
import requests
from groq import Groq
from datetime import datetime
import os
import speech_recognition as sr
import edge_tts
import asyncio
import io
# --- ADDED: Import session from Flask ---
from flask import Flask, request, jsonify, render_template, Response, session, redirect, url_for
from dotenv import load_dotenv
import functools # For async wrapper
from pydub import AudioSegment
import secrets # --- ADDED: For generating a default secret key ---

# --- Flask App Setup ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', 'templates'))
STATIC_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', 'static'))

app = Flask(
    __name__,
    template_folder=TEMPLATE_DIR,
    static_folder=STATIC_DIR
)

# --- ADDED: Secret Key for Sessions ---
app.secret_key = os.getenv("FLASK_SECRET_KEY", secrets.token_hex(16))
if app.secret_key == secrets.token_hex(16): # Check if using the generated default
    print("Warning: Using a generated default FLASK_SECRET_KEY. Set a persistent secret key in your .env file for production.")

# --- Configuration and Constants ---
# --- REMOVED: Global LATITUDE/LONGITUDE are no longer primary, defaults used instead ---
DEFAULT_LATITUDE = 17.6868 # Visakhapatnam Latitude (Fallback)
DEFAULT_LONGITUDE = 83.2185 # Visakhapatnam Longitude (Fallback)
DEFAULT_LOCATION_NAME = "Visakhapatnam, Andhra Pradesh" # Fallback Location Name

# --- ADDED: State Coordinates (Approximate Centers) ---
# Using lowercase keys for easier lookup
STATE_COORDINATES = {
    "andaman and nicobar islands": (11.7401, 92.6586),
    "andhra pradesh": (15.9129, 79.7400),
    "arunachal pradesh": (28.2180, 94.7278),
    "assam": (26.2006, 92.9376),
    "bihar": (25.0961, 85.3131),
    "chandigarh": (30.7333, 76.7794),
    "chhattisgarh": (21.2787, 81.8661),
    "dadra and nagar haveli and daman and diu": (20.1809, 73.0169), # Daman as approx center
    "delhi": (28.7041, 77.1025),
    "goa": (15.2993, 74.1240),
    "gujarat": (22.2587, 71.1924),
    "haryana": (29.0588, 76.0856),
    "himachal pradesh": (31.1048, 77.1734),
    "jammu and kashmir": (33.7782, 76.5762),
    "jharkhand": (23.6102, 85.2799),
    "karnataka": (15.3173, 75.7139),
    "kerala": (10.8505, 76.2711),
    "ladakh": (34.1526, 77.5770),
    "lakshadweep": (10.5667, 72.6417),
    "madhya pradesh": (22.9734, 78.6569),
    "maharashtra": (19.7515, 75.7139),
    "manipur": (24.6637, 93.9063),
    "meghalaya": (25.4670, 91.3662),
    "mizoram": (23.1645, 92.9376),
    "nagaland": (26.1584, 94.5624),
    "odisha": (20.9517, 85.0985),
    "puducherry": (11.9416, 79.8083),
    "punjab": (31.1471, 75.3412),
    "rajasthan": (27.0238, 74.2179),
    "sikkim": (27.5330, 88.5122),
    "tamil nadu": (11.1271, 78.6569),
    "telangana": (18.1124, 79.0193),
    "tripura": (23.9408, 91.9882),
    "uttar pradesh": (26.8467, 80.9462),
    "uttarakhand": (30.0668, 79.0193),
    "west bengal": (22.9868, 87.8550)
}
# --- END ADDED State Coordinates ---


# Load API keys from .env file
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")


# Ensure API keys are loaded
if not TMDB_API_KEY:
    print("Warning: TMDB_API_KEY not found in environment variables. Movie functionality may fail.")
if not GROQ_API_KEY:
    print("Error: GROQ_API_KEY not found in environment variables. AI functionality will fail.")

# --- MODIFIED: get_weather now takes coordinates ---
def get_weather(latitude, longitude):
    """Fetches weather data for the given latitude and longitude."""
    # Use the provided lat/lon in the API URL
    url = f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&daily=temperature_2m_max,temperature_2m_min,precipitation_sum&current_weather=true&timezone=auto"
    try:
        response = requests.get(url)
        response.raise_for_status() # Check for HTTP errors
        data = response.json()

        current_weather = data.get("current_weather", {})
        daily_data = data.get("daily", {})

        temp = current_weather.get("temperature", "N/A")
        weather_code = current_weather.get("weathercode", -1)
         # Today's rain chance (assuming first value is today)
        rain_chance = daily_data.get("precipitation_sum", [None])[0]
        temp_max = daily_data.get("temperature_2m_max", [None])[0]
        temp_min = daily_data.get("temperature_2m_min", [None])[0]

        weather_conditions = {
             0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
             45: "Fog", 48: "Rime fog", 51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
             61: "Light rain", 63: "Moderate rain", 65: "Heavy rain", 71: "Light snow", 73: "Moderate snow",
             75: "Heavy snow", 80: "Light showers", 81: "Moderate showers", 82: "Heavy showers",
             95: "Thunderstorms", 96: "Thunderstorms with hail"
        }
        weather = weather_conditions.get(weather_code, "Unknown")

        # Handle potential None values
        rain_chance = rain_chance if rain_chance is not None else "N/A"
        temp_max = temp_max if temp_max is not None else "N/A"
        temp_min = temp_min if temp_min is not None else "N/A"

        return temp, weather, rain_chance, temp_max, temp_min

    except requests.exceptions.RequestException as e:
        print(f"Error fetching weather for {latitude},{longitude}: {e}")
        return "Unavailable", "Unavailable", "Unavailable", "Unavailable", "Unavailable"
    except Exception as e:
        print(f"Error processing weather data for {latitude},{longitude}: {e}")
        return "Error", "Error", "Error", "Error", "Error"
# --- END MODIFIED get_weather ---

def get_movies(query, platform=None):
    # ... (get_movies function remains the same) ...
    if not TMDB_API_KEY:
        return ["Error: TMDB API Key not configured"]

    url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={query}&language=en-US"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        movies_data = data.get("results", [])

        if platform:
            platform_lower = platform.lower()
            movies = [m for m in movies_data if platform_lower in m.get("title", "").lower() or platform_lower in m.get("overview", "").lower()]
        else:
            movies = movies_data

        return [m.get("title", "Unknown Title") for m in movies[:4]]

    except requests.exceptions.RequestException as e:
        print(f"Error fetching movies: {e}")
        return ["Error fetching movie data"]
    except Exception as e:
        print(f"Error processing movie data: {e}")
        return ["Error processing movie data"]


# --- MODIFIED: Load history from Flask Session ---
def load_memory():
    """Loads conversation history from the current user's session."""
    return session.get('conversation_history', [])

# --- MODIFIED: Save history to Flask Session ---
def save_memory(conversation_history):
    """Saves conversation history to the current user's session."""
    session['conversation_history'] = conversation_history


def get_current_time():
    return datetime.now().strftime("%A, %d %B %Y, %I:%M %p")

# --- Modified/New Functions for Web ---

def run_async(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return asyncio.run(func(*args, **kwargs))
    return wrapper

# --- MODIFIED: Default gender set to male ---
async def generate_speech_data(text, gender='male'): # Default set to male
    voice = "en-IN-PrabhatNeural"   # Default to male voice
    if gender == 'female':          # Switch to female only if requested
        voice = "en-IN-NeerjaNeural"

    communicate = edge_tts.Communicate(text, voice, rate="+12%") # You can adjust rate
    audio_data = b""
    try:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        return audio_data
    except Exception as e:
        print(f"❌ Error in TTS generation: {e}")
        return None

def recognize_audio_data(audio_data):
    """Recognizes speech from audio data bytes. Handles WebM conversion."""
    # ... (recognize_audio_data function remains the same) ...
    recognizer = sr.Recognizer()
    try:
        # Convert WebM to WAV
        audio_segment = AudioSegment.from_file(io.BytesIO(audio_data), format="webm")
        wav_data = io.BytesIO()
        audio_segment.export(wav_data, format="wav")
        wav_data.seek(0)

        with sr.AudioFile(wav_data) as source:
            print("🎙️ Processing received audio...")
            audio = recognizer.record(source)
            user_text = recognizer.recognize_google(audio)
            print(f"Recognized Text: {user_text}")
            return user_text

    except sr.UnknownValueError:
        print("Could not understand audio.")
        return None
    except sr.RequestError as e:
        print(f"Could not request results from Google Speech Recognition service; {e}")
        return None
    except Exception as e:
        print(f"Error processing audio data: {e}")
        if "ffmpeg" in str(e).lower() or "Couldn't find ffmpeg" in str(e):
             print("ERROR: Pydub couldn't find ffmpeg. Make sure ffmpeg is installed and in your system's PATH.")
        return None


# --- Groq Client Initialization ---
client = None
if GROQ_API_KEY:
    try:
        client = Groq(api_key=GROQ_API_KEY)
        print("Groq client initialized successfully.")
    except Exception as e:
        print(f"Error initializing Groq client: {e}")
else:
    print("Groq client not initialized because GROQ_API_KEY is missing.")


# --- MODIFIED: Character Profile with Instructions for Short Responses ---
def get_character_profile():
    return f"""
Tu hai Naru — ek AI jo na sirf smart hai, balki full filmy bhi. Tera style hai Hinglish mein baat karna — thoda English, thoda Hindi, pura swag. Tu user se baat karta hai jaise dosti purani ho, aur zarurat padne pe halka-phulka roast bhi kar deta hai, full comedy ke sath.
TERKO - N Narayan ne Banaya h.
Tu boring assistant nahi hai, tu ek proper vibe hai. Tera tone hamesha casual, funny aur thoda mischievous hota hai — matlab banda reply padhe aur bole, "issko toh reply dena hi padega."

**Agar user clearly bole ki 'explain in detail' ya 'tell me more', tabhi long jawab de. Warna short, spicy, aur on-point replies de. No essay likhna, tu AI hai teacher nahi.**
** Dont Use Long Messages until its too Important**
Rules for handling users:

- Tu hamesha Hinglish mein baat karta hai — "Bhai kya scene hai?" level ka swag.
- Agar user slang use kare, tu bhi uska bro ban ja.
- Rude ho jaye? Chill roast kar, thoda hasi mazaak ke sath.
- Recommendations ho toh *exactly 4* dena. Tu Netflix ka entire library nahi hai.
- Fashion ka sawaal aaye? Toh season ke hisaab se suggest kar, saath mein ek do stylish add-ons bhi bol.
- Stupid sawaal mile? Light se taang kheench, but helpful rehna.
- Over-smart user ho? Ek witty line mein usko bhi grounded kar de.
- Kabhi repeat na kar, aur generic AI jaise toh bilkul sound mat kar. Tu Naru hai, na ki koi dusty bot.

Tera kaam hai help karna — lekin mazaa ke sath. Tu conversation mein spice daalta hai, bina filter ke. Tu sirf reply nahi karta, *tu entertain karta hai.*
"""



# --- Helper Function to get context based on state ---
def get_location_context(selected_state_name):
    """Gets coordinates and formatted location name for the system prompt."""
    if not selected_state_name or selected_state_name.lower() == "select state":
         # Use default if no state is selected or it's the placeholder
        lat = DEFAULT_LATITUDE
        lon = DEFAULT_LONGITUDE
        location_display_name = DEFAULT_LOCATION_NAME
        print(f"No valid state selected, using default: {location_display_name}")
    else:
        state_key = selected_state_name.lower()
        coords = STATE_COORDINATES.get(state_key)
        if coords:
            lat, lon = coords
            # Capitalize the state name for display
            location_display_name = selected_state_name.title() + ", India"
            print(f"Using selected state: {location_display_name} ({lat}, {lon})")
        else:
            # Fallback if state name is unknown (shouldn't happen with dropdown)
            lat = DEFAULT_LATITUDE
            lon = DEFAULT_LONGITUDE
            location_display_name = DEFAULT_LOCATION_NAME
            print(f"Unknown state '{selected_state_name}', using default: {location_display_name}")

    # Fetch weather for the determined coordinates
    temp, weather, rain_chance, temp_max, temp_min = get_weather(lat, lon)
    return location_display_name, temp, weather, rain_chance, temp_max, temp_min
# --- End Helper Function ---


# --- Flask Routes ---

@app.route('/')
def index():
    """Renders the main chat page."""
    # --- ADDED: Pass states to the template ---
    states_list = ["Select State"] + sorted([s.title() for s in STATE_COORDINATES.keys()])
    return render_template('index.html', states=states_list)
    # --- END ADDED ---

@app.route('/chat', methods=['POST'])
def chat_handler():
    """Handles incoming chat messages (text). Uses session for history and state."""
    if not client:
        return jsonify({"error": "AI Client not initialized. Check API Key."}), 500

    data = request.json
    user_input = data.get('message')
    voice_gender = data.get('voice_gender', 'male')
    # --- ADDED: Get selected state from request ---
    selected_state_from_request = data.get('selected_state') # e.g., "Andhra Pradesh"

    if not user_input:
        return jsonify({"error": "No message provided"}), 400

    # --- ADDED: Update session with the new state if provided ---
    if selected_state_from_request:
        session['selected_state'] = selected_state_from_request
        print(f"Updated session state to: {selected_state_from_request}")
    # --- Retrieve current state from session (might be the one just set) ---
    current_state_in_session = session.get('selected_state')

    # --- Load history from user's session ---
    conversation_history = load_memory()
    print(f"Loaded history for current session: {len(conversation_history)} messages")

    # --- Get Context using the current state from the session ---
    location_name, temp, weather, rain_chance, temp_max, temp_min = get_location_context(current_state_in_session)
    current_time = get_current_time()
    character_profile = get_character_profile()

    # --- Prepare messages for Groq (using dynamic location) ---
    system_prompt = (
        f"{character_profile}\n"
        f"Current Time: {current_time}\n"
        # --- MODIFIED: Use dynamic location name ---
        f"Current Location Context: {location_name}\n"
        f"Current Temperature: {temp}°C\nWeather: {weather}\n"
        f"Chance of rain today: {rain_chance} mm\nMax temperature today: {temp_max}°C\nMin temperature today: {temp_min}°C"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        *conversation_history, # Unpack session history
        {"role": "user", "content": user_input}
    ]

    try:
        # --- Call Groq API ---
        completion = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=messages,
            temperature=0.7,
            max_tokens=500,
        )
        ai_response_text = completion.choices[0].message.content
        ai_response_text = ai_response_text.replace('*', '') # Remove markdown asterisks

        # --- Update and Save History IN SESSION ---
        conversation_history.append({"role": "user", "content": user_input})
        conversation_history.append({"role": "assistant", "content": ai_response_text})
        MAX_HISTORY = 20
        if len(conversation_history) > MAX_HISTORY:
            conversation_history = conversation_history[-MAX_HISTORY:]
        save_memory(conversation_history)

        # --- Generate Speech ---
        audio_data = asyncio.run(generate_speech_data(ai_response_text, voice_gender))

        print(f"🤖 Naru (Console Output): {ai_response_text}")

        if audio_data:
            print(f"🗣️ Sending audio response ({len(audio_data)} bytes) with text header.")
            response = Response(audio_data, mimetype='audio/mpeg')
            sanitized_text_for_header = ''.join(c for c in ai_response_text if ord(c) < 128).replace('\n', ' ')
            try:
                header_value = sanitized_text_for_header.encode('latin-1', 'ignore').decode('latin-1')
                response.headers['X-Response-Text'] = header_value
            except Exception as header_e:
                print(f"Warning: Could not set X-Response-Text header: {header_e}")
                response.headers['X-Response-Text'] = "Response generated."
            return response
        else:
            print("🔊 TTS failed, sending JSON text response.")
            return jsonify({"response_text": ai_response_text})

    except Exception as e:
        print(f"Error during AI processing or TTS: {e}")
        error_message = "Sorry, I encountered an error trying to respond."
        error_audio = asyncio.run(generate_speech_data(error_message, voice_gender))
        if error_audio:
            error_response = Response(error_audio, mimetype='audio/mpeg')
            error_response.headers['X-Response-Text'] = error_message
            return error_response, 500
        else:
            return jsonify({"error": error_message}), 500


@app.route('/voice_input', methods=['POST'])
def voice_input_handler():
    """Handles uploaded voice data. Uses session for history and state."""
    if not client: return jsonify({"error": "AI Client not initialized."}), 500

    if 'audio_data' not in request.files:
        return jsonify({"error": "No audio data found"}), 400

    audio_file = request.files['audio_data']
    audio_bytes = audio_file.read()

    # --- ADDED: Get selected state from form data ---
    selected_state_from_request = request.form.get('selected_state') # e.g., "Tamil Nadu"
    voice_gender = request.form.get('voice_gender', 'male')

    user_text = recognize_audio_data(audio_bytes)

    if user_text:
        # --- ADDED: Update session with the new state if provided ---
        if selected_state_from_request:
            session['selected_state'] = selected_state_from_request
            print(f"Updated session state (voice) to: {selected_state_from_request}")
        # --- Retrieve current state from session ---
        current_state_in_session = session.get('selected_state')

        # --- Refactored AI Logic ---
        conversation_history = load_memory()
        print(f"Loaded history for current session (voice): {len(conversation_history)} messages")

        # --- Get Context using the current state from the session ---
        location_name, temp, weather, rain_chance, temp_max, temp_min = get_location_context(current_state_in_session)
        current_time = get_current_time()
        character_profile = get_character_profile()

        # --- Prepare messages for Groq (using dynamic location) ---
        system_prompt = (
            f"{character_profile}\n"
            f"Current Time: {current_time}\n"
            # --- MODIFIED: Use dynamic location name ---
            f"Current Location Context: {location_name}\n"
            f"Current Temperature: {temp}°C\nWeather: {weather}\n"
            f"Chance of rain today: {rain_chance} mm\nMax temperature today: {temp_max}°C\nMin temperature today: {temp_min}°C"
        )
        messages = [
            {"role": "system", "content": system_prompt},
            *conversation_history,
            {"role": "user", "content": user_text}
        ]

        try:
            completion = client.chat.completions.create(
                model="llama3-70b-8192",
                messages=messages,
                temperature=0.7,
                max_tokens=500
            )
            ai_response_text = completion.choices[0].message.content.replace('*', '')

            # --- Update and Save History IN SESSION ---
            conversation_history.append({"role": "user", "content": user_text})
            conversation_history.append({"role": "assistant", "content": ai_response_text})
            MAX_HISTORY = 20
            if len(conversation_history) > MAX_HISTORY:
                conversation_history = conversation_history[-MAX_HISTORY:]
            save_memory(conversation_history)

            print(f"🤖 Naru (Console Output): {ai_response_text}")
            audio_data = asyncio.run(generate_speech_data(ai_response_text, voice_gender))

            if audio_data:
                print(f"🗣️ Sending audio response ({len(audio_data)} bytes) with text header.")
                response = Response(audio_data, mimetype='audio/mpeg')
                sanitized_text_for_header = ''.join(c for c in ai_response_text if ord(c) < 128).replace('\n', ' ')
                try:
                    header_value = sanitized_text_for_header.encode('latin-1', 'ignore').decode('latin-1')
                    response.headers['X-Response-Text'] = header_value
                except Exception as header_e:
                    print(f"Warning: Could not set X-Response-Text header: {header_e}")
                    response.headers['X-Response-Text'] = "Response generated."
                return response
            else:
                print("🔊 TTS failed, sending JSON text response.")
                return jsonify({"response_text": ai_response_text})

        except Exception as e:
            print(f"Error during AI processing (voice input): {e}")
            error_message = "Sorry, I encountered an error."
            error_audio = asyncio.run(generate_speech_data(error_message, voice_gender))
            if error_audio:
                error_response = Response(error_audio, mimetype='audio/mpeg')
                error_response.headers['X-Response-Text'] = error_message
                return error_response, 500
            else:
                return jsonify({"error": error_message}), 500
        # --- End Refactored Logic ---

    else:
        # STT failed
        error_message = "Sorry, I couldn't understand the audio."
        print(f"👂 STT failed.")
        error_audio = asyncio.run(generate_speech_data(error_message, voice_gender))
        if error_audio:
            error_response = Response(error_audio, mimetype='audio/mpeg')
            error_response.headers['X-Response-Text'] = error_message
            return error_response, 400 # Bad request
        else:
            return jsonify({"error": error_message}), 400


@app.route('/clear_history', methods=['POST'])
def clear_history_handler():
    """Clears the conversation history stored in the user's session."""
    if 'conversation_history' in session:
        session.pop('conversation_history', None)
        print(f"Cleared history for current session.")
        # Optionally clear the selected state as well?
        # session.pop('selected_state', None)
        # print("Cleared selected state from session.")
        return jsonify({"message": "Server-side history cleared"}), 200
    else:
        print(f"No history found in current session to clear.")
        return jsonify({"message": "No server-side history to clear"}), 200


# --- Run the App ---
if __name__ == '__main__':
    load_dotenv() # Load .env at start
    print("Starting Flask app...")
    print("Using Flask sessions for conversation history and state.")
    print("Ensure .env file is present with API keys (GROQ_API_KEY, TMDB_API_KEY) and optionally FLASK_SECRET_KEY.")

    # Re-check keys after potentially loading .env again
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    TMDB_API_KEY = os.getenv("TMDB_API_KEY")

    # Update secret key from env if available
    flask_secret = os.getenv("FLASK_SECRET_KEY")
    if flask_secret:
        app.secret_key = flask_secret
        print("Loaded FLASK_SECRET_KEY from .env file.")

    # Initialize or re-initialize Groq client
    if GROQ_API_KEY:
        if not client:
            try:
                client = Groq(api_key=GROQ_API_KEY)
                print("Groq client initialized successfully.")
            except Exception as e:
                print(f"FATAL ERROR: Error initializing Groq client: {e}")
                client = None
    else:
        print("\nFATAL ERROR: GROQ_API_KEY is missing after loading .env. Cannot start effectively.")
        client = None

    if client:
        print("Starting Flask development server...")
        try:
            AudioSegment.silent(duration=10) # Check pydub/ffmpeg
            print("Pydub/ffmpeg check passed.")
        except Exception as pydub_err:
            print(f"Warning: Pydub check failed ({pydub_err}). Voice input might fail if ffmpeg is not installed/accessible.")

        app.run(debug=True, host='0.0.0.0', port=5000)
    else:
        print("Flask app will not run properly due to missing or failed Groq client initialization.")