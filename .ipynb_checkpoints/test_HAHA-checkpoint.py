# backend/main.py
from flask import Flask, request, send_file, jsonify
import os
import uuid
import subprocess
import urllib.request

# 🔽 Download soundfont if it's missing
SOUNDFONT_FILE = "FluidR3_GM.sf2"
SOUNDFONT_URL = "https://drive.google.com/uc?export=download&id=1mxi3Sa2t2hUqQ50hBw1BKGffPzSlIplD"

if not os.path.exists(SOUNDFONT_FILE):
    print("🎵 Downloading FluidR3_GM.sf2...")
    try:
        urllib.request.urlretrieve(SOUNDFONT_URL, SOUNDFONT_FILE)
        print("✅ SoundFont downloaded successfully.")
    except Exception as e:
        print(f"❌ Failed to download SoundFont: {e}")



app = Flask(__name__)

# ✅ Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
SOUNDFONT_PATH = os.path.join(BASE_DIR, "FluidR3_GM.sf2")  # full path to soundfont
MIN_FILE_SIZE = 10  # bytes

# ✅ Ensure output/ exists
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)


@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json()
    lilypond_code = data.get("lilypond")
    requested_filename = data.get("filename") or str(uuid.uuid4())
    
    # Sanitise filename: remove bad characters, enforce safe format
    filename = "".join(c for c in requested_filename if c.isalnum() or c in ("_", "-")).rstrip()

    if not lilypond_code:
        return jsonify({"error": "Missing LilyPond code"}), 400

    # Paths
    ly_path = os.path.join(OUTPUT_DIR, f"{filename}.ly")
    pdf_path = os.path.join(OUTPUT_DIR, f"{filename}.pdf")
    midi_path = os.path.join(OUTPUT_DIR, f"{filename}.midi")
    mp3_path = os.path.join(OUTPUT_DIR, f"{filename}.mp3")
    wav_path = os.path.join(OUTPUT_DIR, f"{filename}.wav")

    # Write .ly file
    with open(ly_path, "w") as f:
        f.write(lilypond_code)

    # Compile with LilyPond
    result = subprocess.run(
        ["lilypond", "-dignore-errors", "-o", os.path.join(OUTPUT_DIR, filename), ly_path],
        capture_output=True,
        text=True
    )
    
    print("🔧 LilyPond stderr:")
    print(result.stderr)
    
    if not os.path.exists(pdf_path) or os.path.getsize(pdf_path) < MIN_FILE_SIZE:
        return jsonify({
            "error": "LilyPond compilation failed",
            "log": result.stderr
        }), 500

    # Check MIDI exists
    if not os.path.exists(midi_path) or os.path.getsize(midi_path) < MIN_FILE_SIZE:
        return jsonify({"error": "MIDI file not generated or too small"}), 500

    # Convert MIDI → WAV → MP3
    try:
        subprocess.run([
            "fluidsynth", "-ni", SOUNDFONT_PATH, midi_path,
            "-F", wav_path, "-r", "44100"
        ], check=True)

        subprocess.run([
            "ffmpeg", "-y", "-i", wav_path, mp3_path
        ], check=True)

        os.remove(wav_path)

    except subprocess.CalledProcessError:
        return jsonify({"error": "MIDI to MP3 conversion failed"}), 500

    if not os.path.exists(mp3_path) or os.path.getsize(mp3_path) < MIN_FILE_SIZE:
        return jsonify({"error": "MP3 file is missing or invalid"}), 500

    return jsonify({
        "pdf_url": f"/download/{filename}.pdf",
        "mp3_url": f"/download/{filename}.mp3"
    })


@app.route("/download/<filename>")
def download(filename):
    path = os.path.join(OUTPUT_DIR, filename)
    if os.path.exists(path) and os.path.getsize(path) > MIN_FILE_SIZE:
        print(f"📤 Sending: {filename}")
        return send_file(path)
    print(f"❌ Missing or invalid file: {filename}")
    return jsonify({"error": "File missing or invalid"}), 500


import openai

openai.api_key = os.environ.get("OPENAI_API_KEY")

@app.route("/generate-lilypond", methods=["POST"])
def generate_lilypond():
    data = request.get_json()
    prompt = data.get("prompt")
    model = data.get("model", "gpt-4o")

    if not prompt:
        return jsonify({"error": "Missing prompt"}), 400

    system_message = {
        "role": "system",
        "content": '''Generate LilyPond (.ly) code for compositions based on the user's prompt. Use exact pitches, not \\relative. Include \\version "2.24.1", a poetic title (make one up if not specified), a composer only if specified, staves with instrument labels using \\set Staff.instrumentName and \\set Staff.shortInstrumentName, proper \\layout {} and \\midi {} blocks inside \\score, valid LilyPond pitch names like bes (not Bb) and fis (not F#), etc. Assign the MIDI instrument using \\set Staff.midiInstrument. Use valid LilyPond syntax that compiles. Use \\header { title = "...", composer = "..." }. Do not include comments, markdown, or explanations.'''
    }

    user_message = {
        "role": "user",
        "content": f"{prompt} – from iOS app."
    }

    try:
        client = openai.OpenAI()  # ⬅️ NEW way to access the API
        
        response = client.chat.completions.create(
            model=model,
            messages=[system_message, user_message],
            temperature=0.7
        )
        
        content = response.choices[0].message.content
        usage = response.usage
        model_used = response.model

        return jsonify({
            "lilypond": content,
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
            "model": model_used
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # app.run(host="0.0.0.0", port=5050, debug=True) # for local Mac backend hosting
    port = int(os.environ.get("PORT", 10000)) # for Render
    app.run(host="0.0.0.0", port=port)

