# backend/main.py
from flask import Flask, request, send_file, jsonify
import os
import uuid
import subprocess
import urllib.request

import re               
import json as json_lib

import openai        


# ✅ Example LilyPond Score to teach GPT the correct format
EXAMPLE_LILYPOND = r"""
\version "2.24.1"

\header {
  title = "Sunlight Through Dissonance"
  composer = "Matt"
}

trumpetOneMusic = {
  \clef treble
  \key aes \major
  <g' b' d''>1
  \bar "|."
}

trumpetTwoMusic = {
  \clef treble
  \key aes \major
  <b' d'' g''>1
  \bar "|."
}

violaMusic = {
  \clef alto
  \key aes \major
  <d' g' b'>1
  \bar "|."
}

pianoRight = {
  \clef treble
  \key aes \major
  <g' b' d''>1
  \bar "|."
}

pianoLeft = {
  \clef bass
  \key aes \major
  <g d g,>1
  \bar "|."
}

\score {
  <<
    \new Staff \with {
      instrumentName = "Trumpet 1"
      shortInstrumentName = "Tpt. 1"
      midiInstrument = "trumpet"
    } { \trumpetOneMusic }

    \new Staff \with {
      instrumentName = "Trumpet 2"
      shortInstrumentName = "Tpt. 2"
      midiInstrument = "trumpet"
    } { \trumpetTwoMusic }

    \new Staff \with {
      instrumentName = "Viola"
      shortInstrumentName = "Vla."
      midiInstrument = "viola"
    } { \violaMusic }

    \new PianoStaff \with {
      instrumentName = "Piano"
      shortInstrumentName = "Pno."
    } <<
      \new Staff \with {
        midiInstrument = "acoustic grand"
      } { \pianoRight }

      \new Staff \with {
        midiInstrument = "acoustic grand"
      } { \pianoLeft }
    >>
  >>
  \layout { }
  \midi { }
}
"""
   

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
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens,
            "model": model_used
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/smart-generate-lilypond", methods=["POST"])
def smart_generate_lilypond():
    data = request.get_json()
    user_prompt = data.get("prompt")
    model = data.get("model", "gpt-4o")

    if not user_prompt:
        return jsonify({"error": "Missing prompt"}), 400

    conversation = [
    {
        "role": "system",
        "content":
            "You are an expert composer.\n\n"
            "When the user requests a musical composition, you must first carefully plan:\n\n"
            "- Style\n"
            "- Form\n"
            "- Key (or 'atonal')\n"
            "- Modulation (if any)\n"
            "- Time Signature\n"
            "- Mood\n"
            "- Texture\n\n"
            "✅ Write the planning clearly inside a ```json``` block.\n\n"
            "✅ Then generate the LilyPond (.ly) code inside a ```lilypond``` block.\n\n"
            "LilyPond Code Rules:\n"
            "- Use exact pitches (no \\relative).\n"
            "- Include \\version, \\header, \\layout, and \\midi blocks.\n"
            "- Include \\score { ... } surrounding the music.\n"
            "- Use valid LilyPond pitch names (e.g., bes not Bb).\n\n"
            "⚡️ Before completing your output, double-check:\n"
            "- You included \\score { ... }\n"
            "- You included \\layout { }\n"
            "- You included \\midi { }\n\n"
            "Here is an example of a correct LilyPond score:\n\n"
            "```" + "lilypond\n" + EXAMPLE_LILYPOND + "\n```" + "\n\n"
            "Follow this style exactly, but generate **new music** based on the user's request.\n\n"
            "NEVER output explanations, comments, or markdown outside code blocks.\n"
            "Only output pure JSON and LilyPond inside code blocks."
    },
    {"role": "user", "content": user_prompt}
]


    def call_gpt():
        client = openai.OpenAI()
        response = client.chat.completions.create(
            model=model,
            messages=conversation,
            temperature=0.7
        )
        return response

    def parse_response(full_text):
        planning_json_match = re.search(r"```json\s*(\{.*?\})\s*```", full_text, re.DOTALL)
        if not planning_json_match:
            return None, None

        planning_json_str = planning_json_match.group(1)
        planning = json_lib.loads(planning_json_str)

        lilypond_code = None
        lilypond_code_match = re.search(r"```lilypond\s*(.*?)\s*```", full_text, re.DOTALL)
        if lilypond_code_match:
            lilypond_code = lilypond_code_match.group(1)
        else:
            parts = full_text.split('```json')
            if len(parts) > 1:
                after_json = parts[1].split('```')[1]
                lilypond_code = after_json.strip()

        return planning, lilypond_code

    try:
        response = call_gpt()
        full_text = response.choices[0].message.content
        usage = response.usage
        model_used = response.model

        planning, lilypond_code = parse_response(full_text)

        if not planning or not lilypond_code:
            return jsonify({"error": "Failed to parse planning or LilyPond", "full_response": full_text}), 500

        required_keywords = ["\\version", "\\header", "\\score", "\\layout", "\\midi"]
        missing_keywords = [kw for kw in required_keywords if kw not in lilypond_code]

        if missing_keywords:
            print("\u26a1\ufe0f Auto-heal: First LilyPond invalid, retrying...")
            response2 = call_gpt()
            full_text2 = response2.choices[0].message.content
            planning2, lilypond_code2 = parse_response(full_text2)

            if planning2 and lilypond_code2:
                planning = planning2
                lilypond_code = lilypond_code2
                usage = response2.usage
                model_used = response2.model

                missing_keywords2 = [kw for kw in required_keywords if kw not in lilypond_code]

                if missing_keywords2:
                    return jsonify({
                        "error": "Auto-heal failed: LilyPond still missing required parts",
                        "missing_sections": missing_keywords2,
                        "lilypond_code": lilypond_code
                    }), 500
            else:
                return jsonify({"error": "Auto-heal failed to parse second attempt"}), 500

        return jsonify({
            "lilypond": lilypond_code,
            "planning": planning,
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens,
            "model": model_used
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/refine-lilypond", methods=["POST"])
def refine_lilypond():
    data = request.get_json()
    current_score = data.get("lilypond")
    edit_prompt = data.get("prompt")
    model = data.get("model", "gpt-4o")

    if not current_score or not edit_prompt:
        return jsonify({"error": "Missing current LilyPond or prompt"}), 400

    messages = [
        {
            "role": "system",
            "content": "You are an expert LilyPond composer and editor. Take the user's existing LilyPond score and apply their requested change while preserving valid syntax. Do not include explanations or markdown—just return updated LilyPond code."
        },
        { "role": "user", "content": f"Here is the current LilyPond score:\n\n{current_score}" },
        { "role": "user", "content": f"Please modify the score: {edit_prompt}" }
    ]

    try:
        client = openai.OpenAI()
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7
        )
        content = response.choices[0].message.content
        usage = response.usage
        model_used = response.model

        return jsonify({
            "lilypond": content,
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens,
            "model": model_used
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # app.run(host="0.0.0.0", port=5050, debug=True) # for local Mac backend hosting
    port = int(os.environ.get("PORT", 10000)) # for Render
    app.run(host="0.0.0.0", port=port)

