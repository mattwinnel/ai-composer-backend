# backend/main.py
from flask import Flask, request, send_file, jsonify
import os
import uuid
import subprocess
import urllib.request

import re
import json as json_lib

import openai

import glob
import random

from openai_utils import log_openai_request

import threading  # 👈 for async job handling

   

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

# ✅ In-memory job store
jobs = {}




# ✅ Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
SOUNDFONT_PATH = os.path.join(BASE_DIR, "FluidR3_GM.sf2")
MIN_FILE_SIZE = 10  # bytes



JOBS_FILE = os.path.join(BASE_DIR, "jobs.json")

def save_jobs_to_file():
    try:
        with open(JOBS_FILE, "w") as f:
            json_lib.dump(jobs, f)
    except Exception as e:
        print(f"❌ Failed to save jobs: {e}")

def load_jobs_from_file():
    global jobs
    try:
        if os.path.exists(JOBS_FILE):
            with open(JOBS_FILE, "r") as f:
                jobs = json_lib.load(f)
                print(f"🔄 Loaded {len(jobs)} jobs from disk")
    except Exception as e:
        print(f"❌ Failed to load jobs: {e}")

load_jobs_from_file()


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


def process_job(job_id):
    job = jobs[job_id]
    try:
        filename = job["filename"]
        lilypond_code = job["lilypond"]

        ly_path = os.path.join(OUTPUT_DIR, f"{filename}.ly")
        pdf_path = os.path.join(OUTPUT_DIR, f"{filename}.pdf")
        midi_path = os.path.join(OUTPUT_DIR, f"{filename}.midi")
        mp3_path = os.path.join(OUTPUT_DIR, f"{filename}.mp3")
        wav_path = os.path.join(OUTPUT_DIR, f"{filename}.wav")

        with open(ly_path, "w") as f:
            f.write(lilypond_code)

        subprocess.run(
            ["lilypond", "-dignore-errors", "-o", os.path.join(OUTPUT_DIR, filename), ly_path],
            check=True
        )

        subprocess.run([
            "fluidsynth", "-ni", SOUNDFONT_PATH, midi_path,
            "-F", wav_path, "-r", "44100"
        ], check=True)

        subprocess.run(["ffmpeg", "-y", "-i", wav_path, mp3_path], check=True)

        if os.path.exists(wav_path):
            os.remove(wav_path)

        job.update({
            "status": "completed",
            "pdf_url": f"/download/{filename}.pdf",
            "mp3_url": f"/download/{filename}.mp3"
        })
        
        save_jobs_to_file()

    except Exception as e:
        job["status"] = "failed"
        job["error"] = str(e)
        
        save_jobs_to_file()

@app.route("/job-status/<job_id>")
def job_status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)


@app.route("/start-generate", methods=["POST"])
def start_generate():
    data = request.get_json()
    lilypond_code = data.get("lilypond")
    requested_filename = data.get("filename") or str(uuid.uuid4())

    if not lilypond_code:
        return jsonify({"error": "Missing LilyPond code"}), 400

    filename = "".join(c for c in requested_filename if c.isalnum() or c in ("_", "-")).rstrip()
    job_id = str(uuid.uuid4())

    jobs[job_id] = {
        "status": "pending",
        "filename": filename,
        "lilypond": lilypond_code,
        "pdf_url": None,
        "mp3_url": None,
        "error": None
    }

    threading.Thread(target=process_job, args=(job_id,)).start()

    return jsonify({"job_id": job_id})


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
    model = data.get("model", "gpt-4.1")
    balance = data.get("balance", 0.0)  # ✅ NEW: get user balance from request

    # ✅ Reject if balance is below $0.99
    if balance < 0.99:
        return jsonify({"error": "Insufficient funds"}), 403

    if not prompt:
        return jsonify({"error": "Missing prompt"}), 400

    system_message = {
        "role": "system",
        "content": '''Generate LilyPond (.ly) code for compositions based on the user's prompt. Use exact pitches, not \\relative. Include \\version "2.24.1", a poetic title (make one up if not specified), a composer only if specified (otherwise DO NOT include a composer), staves with instrument labels using \\set Staff.instrumentName and \\set Staff.shortInstrumentName, proper \\layout {} and \\midi {} blocks inside \\score, valid LilyPond pitch names like bes (not Bb) and fis (not F#), etc. Assign the MIDI instrument using \\set Staff.midiInstrument. Use valid LilyPond syntax that compiles. Use \\header { title = "...", composer = "..." }. Do not include comments, markdown, or explanations. Do not include any comments (e.g., lines starting with %). Absolutely no `%` symbols should appear in the output LilyPond code. All output must be pure code only, with no comments.'''
    }

    user_message = {
        "role": "user",
        "content": f"{prompt} – from iOS app."
    }

    try:
        client = openai.OpenAI()  # ⬅️ NEW way to access the API
        
        response = log_openai_request(
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


def run_smart_generation(user_prompt, model, balance):
    import re
    import json as json_lib
    import glob
    import random
    from openai_utils import log_openai_request

    if balance < 0.99:
        raise ValueError("Insufficient funds")

    NUM_ITERATIONS = 1

    EXAMPLE_SCORES_DIR = os.path.join(BASE_DIR, "example_scores")
    example_files = glob.glob(os.path.join(EXAMPLE_SCORES_DIR, "example_score_*.ly"))
    if not example_files:
        raise RuntimeError("No example_score_*.ly files found")

    random_example_path = random.choice(example_files)
    with open(random_example_path, "r", encoding="utf-8") as f:
        example_lilypond = f.read()

    conversation = [
        {
            "role": "system",
            "content":
                "You are an expert composer.\n\n"
                "When the user requests a musical composition, you must first carefully plan (don't be so generic, not always C major and 6/8 time):\n\n"
                "- Style\n"
                "- Form\n"
                "- Key (or 'atonal')\n"
                "- Modulation (if any)\n"
                "- Time Signature\n"
                "- Mood\n"
                "- Upbeat (or not)\n"
                "- Texture\n\n"
                "✅ Write the planning clearly inside a ```json``` block, but convert all values (including booleans, numbers, and enums) to strings. For example: \\\"Upbeat\\\": \\\"true\\\" or \\\"Upbeat\\\": \\\"false\\\"."
                "⚠️ You must escape all backslashes correctly in JSON (e.g., use \"A\\\\B\\\\A'\" instead of \"A\\B\\A'\"). Only return valid JSON.\n\n"
                "All values inside the ```json``` block must be plain strings — not LilyPond syntax."
                "✅ Then generate the LilyPond (.ly) code inside a ```lilypond``` block.\n\n"
                "LilyPond Code Rules:\n"
                "only include a composer if specified (otherwise DO NOT include a composer)"
                "- Use exact pitches (no \\relative).\n"
                "- Include \\version, \\header, \\layout, and \\midi blocks.\n"
                "- Include \\score { ... } surrounding the music.\n"
                "- Use valid LilyPond pitch names (e.g., bes not Bb).\n\n"
                "- Include a tempo indication (such as a descriptive word or a numerical marking) using \\\\tempo near the beginning of the score. Choose a value that matches the character and pacing of the piece.\n"
                "- Use dynamics (e.g., \\\\p, \\\\f, \\\\mf) and expressive markings (e.g., phrasing hairpins, text expressions with \\\\markup) that support the musical shape and intention.\n"
                "- Add phrasing slurs and articulations (e.g., staccato, accents) to clarify musical expression and performance details."
                "⚡️ Before completing your output, double-check:\n"
                "- You included \\score { ... }\n"
                "- You included \\layout { }\n"
                "- You included \\midi { }\n\n"
                "If lyrics are needed, define a variable like \\verseLyrics (do not use \\lyrics), then connect it using \\new Lyrics \\lyricsto \"voiceName\" \\verseLyrics. Always define the melody as a separate variable (e.g., melody = { ... }) before using it inside \\new Voice = \"voiceName\" { \\melody }, so lyrics can attach correctly."
                "Base the harmonic structure on the following (use it as a close guide!!):\n\n"
                "```lilypond\n" + example_lilypond + "\n```" + "\n\n"
                "NEVER output explanations, comments, or markdown outside code blocks.\n"
                "Only output pure JSON and LilyPond inside code blocks.\n\n"
                "Following the original plan, add a melody over the harmony using chord tones as a base."
                "Do not change the style, form, or key unless the plan specifies it. "
                "Make the melody interesting and distinct compared to other voices. Think: movement, contrast, rests, quavers, ties, suspensions, syncopation, unity. "
                "Ensure rhythmic interest. Avoid voice doubling. Use exact pitch and valid LilyPond syntax."
                "Add syncopation, triplets, arpeggios, scalic runs, suspensions, and phrasing rests. "
                "Introduce pedal tones where appropriate. Ensure all voices contribute to the texture and maintain proper voice-leading."
                "Ensure:\n"
                "- rhythmic contrast and interest throughout\n"
                "- expressive melodic phrasing\n"
                "- inner voices with variation (triplets, pedal tones, arpeggiation)\n"
                "- motivic unity\n"
                "- use of phrasing rests\n"
                "Finalize the composition. Confirm it matches the original plan. Make the music coherent, expressive, and formally satisfying. "
                "Double-check that the LilyPond code includes \\version, \\header, \\layout, \\midi, and \\score { ... } and compiles correctly."
                "Fix the score: ensure all measures add up to the correct duration, synchronize all parts bar-by-bar, and align voices so they finish together."
                "Always follow the formatting style used in the example score above. "
                "Each LilyPond command (e.g., \\\\version, \\\\header, variable = { ... }, \\\\score { ... }) must start on its own line. "
                "Never place multiple commands on the same line. "
                "Match the indentation and spacing style exactly."
                "Use the example score as a strict formatting template. Do not deviate from its structure or layout style."
                "Do not include any comments (e.g., lines starting with %). Absolutely no `%` symbols should appear in the output LilyPond code. All output must be pure code only, with no comments."
        },
        {"role": "user", "content": user_prompt}
    ]

    def parse_response(full_text):
        planning_json_match = re.search(r"```json\s*(\{.*?\})\s*```", full_text, re.DOTALL)
        lilypond_match = re.search(r"```lilypond\s*(.*?)\s*```", full_text, re.DOTALL)

        planning = json_lib.loads(planning_json_match.group(1)) if planning_json_match else None
        lilypond = lilypond_match.group(1).strip() if lilypond_match else None
        return planning, lilypond

    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_tokens = 0

    planning = None
    lilypond_code = None
    versions = []
    all_messages = []

    for i in range(1, NUM_ITERATIONS + 1):
        if i == 1:
            messages = conversation
        else:
                if i == 2:
                    refine_prompt = (
                        "Following the original plan, add a melody over the harmony using chord tones as a base."
                        "Do not change the style, form, or key unless the plan specifies it. "
                        "Make the melody interesting and distinct compared to other voices. Think: movement, contrast, rests, quavers, ties, suspensions, syncopation, unity. "
                        "Ensure rhythmic interest. Avoid voice doubling. Use exact pitch and valid LilyPond syntax."
                    )
                elif i == 3:
                    refine_prompt = (
                        "Following the plan, enhance the inner and lower voices for greater musical and rhythmic interest. "
                        "Add syncopation, triplets, arpeggios, scalic runs, suspensions, and phrasing rests. "
                        "Introduce pedal tones where appropriate. Ensure all voices contribute to the texture and maintain proper voice-leading."
                    )
                elif i == 4:
                    refine_prompt = (
                        "Continue following the original plan. Refine the composition for musical expressiveness, rhythmic vitality, and structural clarity. "
                        "Ensure:\n"
                        "- rhythmic contrast and interest throughout\n"
                        "- expressive melodic phrasing\n"
                        "- inner voices with variation (triplets, pedal tones, arpeggiation)\n"
                        "- motivic unity\n"
                        "- use of phrasing rests\n"
                        "Ensure the LilyPond code compiles, uses exact pitch, and follows formatting rules."
                    )
                elif i == 5:
                    refine_prompt = (
                        "Finalize the composition. Confirm it matches the original plan. Make the music coherent, expressive, and formally satisfying. "
                        "Double-check that the LilyPond code includes \\version, \\header, \\layout, \\midi, and \\score { ... } and compiles correctly."
                        "Fix the score: ensure all measures add up to the correct duration, synchronize all parts bar-by-bar, and align voices so they finish together."
                    )

                messages = [
                    {
                        "role": "system",
                        "content": (
                            "You are an expert LilyPond composer and editor. When refining a composition, follow the user's original plan exactly. "
                            "Use German note names (e.g., fis, bes), exact pitch (no \\relative), and avoid parallel 5ths/8ves. "
                            "Ensure rhythmic and melodic variety, structural balance, and musical interest in all voices. "
                            "Wrap the music in a valid \\score block with \\layout and \\midi. "
                            "Output valid LilyPond code only — no explanations or extra comments."
                        )
                    },
                    {"role": "user", "content": f"The user's original musical prompt:\n\n{user_prompt}"},
                    {"role": "user", "content": f"Here is the plan we made before composing:\n\n{json_lib.dumps(planning, indent=2)}"},
                    {"role": "user", "content": f"Here is the current LilyPond score:\n\n{lilypond_code}"},
                    {"role": "user", "content": refine_prompt}
                ]

        all_messages.append({"iteration": i, "messages": messages})

        response = log_openai_request(model=model, messages=messages, temperature=0.7)
        content = response.choices[0].message.content.strip()
        usage = response.usage
        model_used = response.model

        total_prompt_tokens += usage.prompt_tokens
        total_completion_tokens += usage.completion_tokens
        total_tokens += usage.total_tokens

        if i == 1:
            planning, lilypond_code = parse_response(content)
            if not planning or not lilypond_code:
                raise ValueError("Initial parsing failed")
        else:
            lilypond_code = content

        versions.append({
            "iteration": i,
            "lilypond": lilypond_code,
            "tokens": {
                "prompt": usage.prompt_tokens,
                "completion": usage.completion_tokens,
                "total": usage.total_tokens
            }
        })

    return {
        "final_lilypond": lilypond_code,
        "planning": planning,
        "iterations": versions,
        "prompt_tokens": total_prompt_tokens,
        "completion_tokens": total_completion_tokens,
        "total_tokens": total_tokens,
        "model": model_used,
        "conversation_history": all_messages
    }


@app.route("/smart-generate-lilypond", methods=["POST"])
def smart_generate_lilypond():
    data = request.get_json()
    try:
        result = run_smart_generation(
            user_prompt=data.get("prompt"),
            model=data.get("model", "gpt-4.1"),
            balance=data.get("balance", 0.0)
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/start-smart-generate", methods=["POST"])
def start_smart_generate():
    data = request.get_json()
    user_prompt = data.get("prompt")
    model = data.get("model", "gpt-4.1")
    balance = data.get("balance", 0.0)

    if not user_prompt:
        return jsonify({"error": "Missing prompt"}), 400

    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "status": "pending",
        "result": None,
        "error": None
    }

    def job_runner():
        try:
            result = run_smart_generation(user_prompt, model, balance)
            jobs[job_id]["status"] = "completed"
            jobs[job_id]["result"] = result
            
            save_jobs_to_file()
            
            
        except Exception as e:
            jobs[job_id]["status"] = "failed"
            jobs[job_id]["error"] = str(e)
            
            save_jobs_to_file()

    threading.Thread(target=job_runner).start()
    return jsonify({"job_id": job_id})


@app.route("/smart-job-status/<job_id>")
def smart_job_status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)




@app.route("/refine-lilypond", methods=["POST"])
def refine_lilypond():
    data = request.get_json()
    current_score = data.get("lilypond")
    edit_prompt = data.get("prompt")
    model = data.get("model", "gpt-4.1")
    balance = data.get("balance", 0.0)  # ✅ NEW: get user balance from request
    
    # 🔁 Load a new random example LilyPond file on each request
    EXAMPLE_SCORES_DIR = os.path.join(BASE_DIR, "example_scores")
    example_files = glob.glob(os.path.join(EXAMPLE_SCORES_DIR, "example_score_*.ly"))
    if not example_files:
        return jsonify({"error": "No example_score_*.ly files found"}), 500

    random_example_path = random.choice(example_files)
    with open(random_example_path, "r", encoding="utf-8") as f:
        example_lilypond = f.read()

    # ✅ Reject if balance is below $0.99
    if balance < 0.99:
        return jsonify({"error": "Insufficient funds"}), 403

    if not current_score or not edit_prompt:
        return jsonify({"error": "Missing current LilyPond or prompt"}), 400
        

    messages = [
        {
    "role": "system",
    "content": (
        "You are an expert LilyPond composer, editor, and engraver. Take the user's LilyPond score and apply their requested change with valid syntax and structure.\n\n"
        "IMPORTANT:\n"
        "✅ If you add new instruments or staves (e.g. Violin, Flute), include them **inside the same `<< ... >>` block** within the `\\score`.\n"
        "keep the footer if there was one"
        "only include a composer if specified (otherwise DO NOT include a composer)"
        "❌ Never leave `\\new Staff` outside the main score grouping.\n"
        "✅ Wrap all staves (Piano, Violin, etc.) inside a single top-level `<< ... >>` block inside the `\\score`.\n\n"
        "To transpose music, wrap it in `\\transpose <from> <to> { ... }` for example to transpose up one octave, wrap the music in `\\transpose c c' { ... }`\n"
        "Use exact pitches (e.g. `c'`, `g''`) instead of `\\relative`\n\n"
        "If lyrics are needed, define a variable like \\verseLyrics (do not use \\lyrics), then connect it using \\new Lyrics \\lyricsto \"voiceName\" \\verseLyrics. Always define the melody as a separate variable (e.g., melody = { ... }) before using it inside \\new Voice = \"voiceName\" { \\melody }, so lyrics can attach correctly."
        "Only return valid LilyPond code. Do not include explanations, comments, markdown, or anything outside the LilyPond code."
        "Do not include any comments (e.g., lines starting with %). Absolutely no `%` symbols should appear in the output LilyPond code. All output must be pure code only, with no comments."
        "Here is an example of good syntax to make sure the output compiles:\n\n"
        "```lilypond\n" + example_lilypond + "\n```" + "\n\n"
    )
}
,
        { "role": "user", "content": f"Here is the current LilyPond score:\n\n{current_score}" },
        { "role": "user", "content": f"Please modify the score: {edit_prompt}" }
    ]

    try:
        client = openai.OpenAI()
        response = log_openai_request(
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
        
        
        
        
@app.route("/smart-full-generate", methods=["POST"])
def smart_full_generate():
    data = request.get_json()
    user_prompt = data.get("prompt")
    model = data.get("model", "gpt-4.1")
    balance = data.get("balance", 0.0)

    if not user_prompt:
        return jsonify({"error": "Missing prompt"}), 400
    if balance < 0.99:
        return jsonify({"error": "Insufficient funds"}), 403

    try:
        # 🔁 Step 1: AI smart generate
        result = run_smart_generation(user_prompt, model, balance)
        lilypond_code = result["final_lilypond"]

        # 🔁 Step 2: Save and render
        filename = "".join(c for c in (data.get("filename") or str(uuid.uuid4())) if c.isalnum() or c in ("_", "-")).rstrip()
        ly_path = os.path.join(OUTPUT_DIR, f"{filename}.ly")
        pdf_path = os.path.join(OUTPUT_DIR, f"{filename}.pdf")
        midi_path = os.path.join(OUTPUT_DIR, f"{filename}.midi")
        mp3_path = os.path.join(OUTPUT_DIR, f"{filename}.mp3")
        wav_path = os.path.join(OUTPUT_DIR, f"{filename}.wav")

        with open(ly_path, "w") as f:
            f.write(lilypond_code)

        subprocess.run(
            ["lilypond", "-dignore-errors", "-o", os.path.join(OUTPUT_DIR, filename), ly_path],
            check=True
        )

        subprocess.run([
            "fluidsynth", "-ni", SOUNDFONT_PATH, midi_path,
            "-F", wav_path, "-r", "44100"
        ], check=True)

        subprocess.run(["ffmpeg", "-y", "-i", wav_path, mp3_path], check=True)

        if os.path.exists(wav_path):
            os.remove(wav_path)

        return jsonify({
            "pdf_url": f"/download/{filename}.pdf",
            "mp3_url": f"/download/{filename}.mp3",
            "lilypond": lilypond_code,
            "planning": result.get("planning"),
            "conversation_history": result.get("conversation_history"),
            "prompt_tokens": result.get("prompt_tokens"),
            "completion_tokens": result.get("completion_tokens"),
            "total_tokens": result.get("total_tokens"),
            "model": result.get("model")
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500
        
        
        
@app.route("/start-smart-full-generate", methods=["POST"])
def start_smart_full_generate():
    data = request.get_json()
    user_prompt = data.get("prompt")
    model = data.get("model", "gpt-4.1")
    balance = data.get("balance", 0.0)
    requested_filename = data.get("filename") or str(uuid.uuid4())

    if not user_prompt:
        return jsonify({"error": "Missing prompt"}), 400
    if balance < 0.99:
        return jsonify({"error": "Insufficient funds"}), 403

    filename = "".join(c for c in requested_filename if c.isalnum() or c in ("_", "-")).rstrip()
    job_id = str(uuid.uuid4())

    jobs[job_id] = {
        "status": "pending",
        "filename": filename,
        "result": None,
        "error": None
    }

    def job_runner():
        try:
            # Step 1: smart generate
            result = run_smart_generation(user_prompt, model, balance)
            lilypond_code = result["final_lilypond"]

            # Step 2: compile LilyPond → PDF/MP3
            ly_path = os.path.join(OUTPUT_DIR, f"{filename}.ly")
            pdf_path = os.path.join(OUTPUT_DIR, f"{filename}.pdf")
            midi_path = os.path.join(OUTPUT_DIR, f"{filename}.midi")
            mp3_path = os.path.join(OUTPUT_DIR, f"{filename}.mp3")
            wav_path = os.path.join(OUTPUT_DIR, f"{filename}.wav")

            with open(ly_path, "w") as f:
                f.write(lilypond_code)

            subprocess.run(
                ["lilypond", "-dignore-errors", "-o", os.path.join(OUTPUT_DIR, filename), ly_path],
                check=True
            )

            subprocess.run([
                "fluidsynth", "-ni", SOUNDFONT_PATH, midi_path,
                "-F", wav_path, "-r", "44100"
            ], check=True)

            subprocess.run(["ffmpeg", "-y", "-i", wav_path, mp3_path], check=True)

            if os.path.exists(wav_path):
                os.remove(wav_path)

            # ✅ Calculate token cost and include it in the result
            prompt_tokens = result.get("prompt_tokens", 0)
            completion_tokens = result.get("completion_tokens", 0)
            model_used = result.get("model", model)
            final_cost = compute_final_cost(prompt_tokens, completion_tokens, model_used)

            # ✅ Save job result with cost
            jobs[job_id].update({
                "status": "completed",
                "pdf_url": f"/download/{filename}.pdf",
                "mp3_url": f"/download/{filename}.mp3",
                "lilypond": lilypond_code,
                "planning": result.get("planning"),
                "conversation_history": result.get("conversation_history"),
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
                "model": model_used,
                "final_cost": final_cost  # ✅ included here
            })

            save_jobs_to_file()

        except Exception as e:
            jobs[job_id]["status"] = "failed"
            jobs[job_id]["error"] = str(e)
            save_jobs_to_file()




    threading.Thread(target=job_runner).start()

    return jsonify({"job_id": job_id})



def compute_final_cost(prompt_tokens, completion_tokens, model):
    # Only rely on actual model identifiers
    if model in ["gpt-4.1-nano"]:  # Basic
        print(f"🟢 Using BASIC pricing for model: {model}")
        input_rate = 0.0001
        output_rate = 0.0004
    else:  # Advanced (e.g., gpt-4.1 or anything else)
        print(f"🔵 Using ADVANCED pricing for model: {model}")
        input_rate = 0.002
        output_rate = 0.008


    openai_tax = 1.20
    profit_multiplier = 10.0
    vat = 1.20

    prompt_cost = (prompt_tokens * input_rate) / 1000
    completion_cost = (completion_tokens * output_rate) / 1000
    base_cost = prompt_cost + completion_cost

    final = base_cost * openai_tax * profit_multiplier * vat
    return round(final, 6)



@app.route("/clear-jobs", methods=["POST"])
def clear_jobs():
    global jobs
    jobs = {}
    save_jobs_to_file()
    return jsonify({"message": "All jobs cleared"}), 200
    
    
if __name__ == "__main__":
    # app.run(host="0.0.0.0", port=5050, debug=True) # for local Mac backend hosting
    port = int(os.environ.get("PORT", 10000)) # for Render
    app.run(host="0.0.0.0", port=port)
