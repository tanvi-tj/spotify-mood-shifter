from urllib import request

import pandas as pd
import numpy as np
import spotipy
from flask import Flask, request, render_template_string
from spotipy.oauth2 import SpotifyOAuth

app = Flask(__name__)

CLIENT_ID = "CLIENT_ID"
CLIENT_SECRET = "CLIENT_SECRET"
REDIRECT_URI = "REDIRECT_URI"
SCOPE = "playlist-modify-public user-read-private"

sp_oauth = SpotifyOAuth(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    redirect_uri=REDIRECT_URI,
    scope=SCOPE
)

NEG_MOODS = ["numb", "sad", "anxious", "angry", "lonely", ]
POS_MOODS = ["calm", "romantic", "confident", "happy", "excited"]

HTML_FORM = """
<form action="/callback" style="max-width: 400px; margin: 50px auto; background-color: #fff0f5; padding: 30px; border-radius: 15px; font-family: 'Segoe UI', sans-serif; box-shadow: 0 10px 25px rgba(0,0,0,0.1);">

    <h2 style="text-align: center; color: #d63384;">💫 Build Your Mood Playlist</h2>

    <label style="font-weight: bold;">Start Mood:</label>
    <select name="start" style="width: 100%; padding: 8px; border-radius: 8px; border: 1px solid #ccc; margin-bottom: 20px;">
        {% for mood in neg_moods %}
        <option value="{{ mood }}">{{ mood.capitalize() }}</option>
        {% endfor %}
    </select>

    <label style="font-weight: bold;">End Mood:</label>
    <select name="end" style="width: 100%; padding: 8px; border-radius: 8px; border: 1px solid #ccc; margin-bottom: 20px;">
        {% for mood in pos_moods %}
        <option value="{{ mood }}">{{ mood.capitalize() }}</option>
        {% endfor %}
    </select>

    <label style="font-weight: bold;">Number of Songs:</label>
    <input type="number" name="steps" value="5" min="3" max="15"
        style="width: 100%; padding: 8px; border-radius: 8px; border: 1px solid #ccc; margin-bottom: 25px;"/>

    <button type="submit"
        style="width: 100%; background-color: #ff69b4; color: white; font-weight: bold; padding: 10px 0; border: none; border-radius: 8px; cursor: pointer;">
        💖 Generate Playlist
    </button>
</form>
"""

@app.route("/")
def index():
    # code = request.args.get("code")
    # token_info = sp_oauth.get_access_token(code)
    # sp = spotipy.Spotify(auth=token_info["access_token"])
    # user = sp.current_user()
    return render_template_string(HTML_FORM, neg_moods=NEG_MOODS, pos_moods=POS_MOODS)


@app.route("/callback")
def callback():
    code = request.args.get("code")
    token_info = sp_oauth.get_access_token(code)
    sp = spotipy.Spotify(auth=token_info["access_token"])

    start_mood = get_mood_info(request.args.get("start"))
    end_mood = get_mood_info(request.args.get("end"))
    no_of_songs = int(request.args.get("steps", 5))

    mood_transition_arc = build_mood_arc(start_mood, end_mood, no_of_songs)

    song_dataset = get_song_dataset()
    playlist = build_playlist(song_dataset, mood_transition_arc)

    playlist_url = create_playlist_from_tracks(
        sp, playlist, request.args.get("start"), request.args.get("end"))

    return f"""
    <div style="max-width: 400px; margin: 80px auto; background-color: #fff0f5; padding: 30px; border-radius: 15px; 
                font-family: 'Segoe UI', sans-serif; text-align: center; box-shadow: 0 10px 25px rgba(0,0,0,0.1);">

        <h2 style="color: #d63384;">🎧 Playlist Created!</h2>
        <p style="font-size: 16px; color: #333;">Your mood arc is live on Spotify</p>

        <a href="{playlist_url}" target="_blank"
           style="display: inline-block; margin-top: 20px; background-color: #ff69b4; color: white;
                  text-decoration: none; padding: 12px 25px; border-radius: 8px; font-weight: bold;">
            💖 Open Playlist
        </a>
    </div>
    """

def create_playlist_from_tracks(sp, track_ids, start_mood, end_mood,
                                description="Your mood-based glow-up playlist"):
    print("Creating playlist...")

    name = "Mood Shifter 💖 " + start_mood.title() + " -> " + end_mood.title()
    user = sp.current_user()
    playlist = sp.user_playlist_create(
        user=user['id'],
        name=name,
        public=True,
        description=description
    )

    # Add tracks to the playlist (in chunks of 100)
    for i in range(0, len(track_ids), 100):
        sp.playlist_add_items(playlist_id=playlist['id'], items=track_ids[i:i+100])

    print(f"🎧 Playlist created: {playlist['external_urls']['spotify']}")
    return playlist['external_urls']['spotify']

def get_song_dataset():
    # Load dataset
    df = pd.read_csv("dataset.csv")
    df = df.dropna(subset=["valence", "energy", "track_name", "artists"])

    artists = [
        "Lana Del Rey", "Taylor Swift", "Dua Lipa", "Ariana Grande",
        "Olivia Rodrigo", "Linkin Park", "Maroon 5", "Billie Eilish",
        "Sabrina Carpenter", "Arctic Monkeys", "Troye Sivan", "Conan Gray"
    ]

    df["artists_clean"] = df["artists"].str.lower()
    df = df[
        df["artists_clean"].apply(lambda a: any(name.lower() in a for name in artists)) &
        (df["popularity"] >= 70)
    ]

    # Remove duplicate track names
    df = df.drop_duplicates(subset=["track_name"])

    return df

def get_mood_info(mood):
    # Valence = musical_positivity(0 = sad / angry, 1 = happy / cheerful)
    # Energy = intensity(0 = chill / sleepy, 1 = loud / fast)

    mood_presets = {

        "numb": {"valence": 0.05, "energy": 0.1},
        "sad": {"valence": 0.2, "energy": 0.3},
        "anxious": {"valence": 0.4, "energy": 0.6},
        "angry": {"valence": 0.1, "energy": 0.9},
        "lonely": {"valence": 0.3, "energy": 0.4},

        "calm": {"valence": 0.8, "energy": 0.3},
        "romantic": {"valence": 0.8, "energy": 0.5},
        "confident": {"valence": 0.9, "energy": 0.8},
        "happy": {"valence": 0.95, "energy": 0.95},
        "excited": {"valence": 0.9, "energy": 1.0},
    }

    return mood_presets[mood]

def cosine_distance(a, b):
    a = np.array(a)
    b = np.array(b)
    return 1 - np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def build_mood_arc(start_mood_info, end_mood_info, steps):
    # Build mood arc
    mood_arc = []
    for i in range(steps):
        v = (start_mood_info["valence"] +
             (end_mood_info["valence"] - start_mood_info["valence"]) * (i / (steps - 1)))
        e = (start_mood_info["energy"] +
             (end_mood_info["energy"] - start_mood_info["energy"]) * (i / (steps - 1)))
        mood_arc.append([v, e])

    return mood_arc

def build_playlist(df, mood_arc, buffer=0.15):
    selected, used_ids = [], set()

    for val, eng in mood_arc:
        pool = df[
            df["valence"].between(val - buffer, val + buffer) &
            df["energy"].between(eng - buffer, eng + buffer) &
            ~df["track_id"].isin(used_ids)
        ]

        if pool.empty:
            pool = df[~df["track_id"].isin(used_ids)].copy()

        pool["distance"] = pool.apply(
            lambda row: cosine_distance(
                [row["valence"], row["energy"]], [val, eng]), axis=1
        )

        best = pool.sort_values("distance").iloc[0]
        selected.append(best)
        used_ids.add(best["track_id"])

    return [row["track_id"] for row in sorted(selected,
                                              key=lambda x: (x["valence"], x["energy"]))]


if __name__ == "__main__":
    app.run(port=8888)

