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

    if not lilypond_code:
        return jsonify({"error": "Missing LilyPond code"}), 400

    # Generate unique file ID
    uid = str(uuid.uuid4())
    ly_path = os.path.join(OUTPUT_DIR, f"{uid}.ly")
    pdf_path = os.path.join(OUTPUT_DIR, f"{uid}.pdf")
    midi_path = os.path.join(OUTPUT_DIR, f"{uid}.midi")
    mp3_path = os.path.join(OUTPUT_DIR, f"{uid}.mp3")

    # Write .ly file
    with open(ly_path, "w") as f:
        f.write(lilypond_code)

    # Compile with LilyPond
    try:
        subprocess.run(["lilypond", "-o", os.path.join(OUTPUT_DIR, uid), ly_path], check=True)
    except subprocess.CalledProcessError:
        return jsonify({"error": "LilyPond compilation failed"}), 500

    # Check MIDI file exists
    if not os.path.exists(midi_path) or os.path.getsize(midi_path) < MIN_FILE_SIZE:
        return jsonify({"error": "MIDI file not generated or too small"}), 500

    # Convert MIDI to WAV using FluidSynth, then convert WAV to MP3 using ffmpeg
    wav_path = os.path.join(OUTPUT_DIR, f"{uid}.wav")
    
    try:
        # Step 1: MIDI → WAV
        subprocess.run([
            "fluidsynth", "-ni", SOUNDFONT_PATH, midi_path,
            "-F", wav_path, "-r", "44100"
        ], check=True)
    
        # Step 2: WAV → MP3
        subprocess.run([
            "ffmpeg", "-y", "-i", wav_path, mp3_path
        ], check=True)
    
        # Optional: remove the WAV file to save space
        # os.remove(wav_path)
    
    except subprocess.CalledProcessError:
        return jsonify({"error": "MIDI to MP3 conversion failed"}), 500


    # Final checks
    if not os.path.exists(pdf_path) or os.path.getsize(pdf_path) < MIN_FILE_SIZE:
        return jsonify({"error": "PDF generation failed"}), 500

    if not os.path.exists(mp3_path) or os.path.getsize(mp3_path) < MIN_FILE_SIZE:
        return jsonify({"error": "MP3 file is missing or invalid"}), 500

    return jsonify({
        "pdf_url": f"/download/{uid}.pdf",
        "mp3_url": f"/download/{uid}.mp3"
    })

@app.route("/download/<filename>")
def download(filename):
    path = os.path.join(OUTPUT_DIR, filename)
    if os.path.exists(path) and os.path.getsize(path) > MIN_FILE_SIZE:
        print(f"📤 Sending: {filename}")
        return send_file(path)
    print(f"❌ Missing or invalid file: {filename}")
    return jsonify({"error": "File missing or invalid"}), 500

if __name__ == "__main__":
    # app.run(host="0.0.0.0", port=5050, debug=True) # for local Mac backend hosting
    port = int(os.environ.get("PORT", 10000)) # for Render
    app.run(host="0.0.0.0", port=port)

