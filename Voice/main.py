import sounddevice as sd
import queue
import json
import os
import sys
import subprocess
import argparse
from dotenv import load_dotenv
import pyttsx3
from vosk import Model, KaldiRecognizer

# ----------------- Setup -----------------
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from Server.Node import Node

this_directory = os.path.dirname(os.path.abspath(__file__))

# Load environment
load_dotenv()
platform = os.getenv("PLATFORM")

# CLI arguments
parser = argparse.ArgumentParser()
parser.add_argument("-v", "--verbose", action="store_true", help="Show all detected speech")
args = parser.parse_args()
VERBOSE = args.verbose

# Node
node = Node("voice", "http://localhost:5000")

# Audio queue
q = queue.Queue()

# ----------------- Constants -----------------
TRIGGER_WORD = "vector"
TRIGGER_WORD_LIST = ["vector","victor","viktor","vicktor","victa","vitker"]
EXIT_WORD = "thank you"

VOICE = "mb-en1"
SPEED = "100"

listenForCommand = False

# ----------------- TTS (Unified) -----------------
engine = None
if platform != "RPI":
    engine = pyttsx3.init()

# espeak -v mb-en1 -s 100 "Hello, world"
def speak(text):
    print(f"[TTS]: {text}")

    if platform == "RPI":
        subprocess.run(["espeak", "-v", VOICE, "-s", SPEED, text])
    else:
        engine.say(text)
        engine.runAndWait()

# ----------------- Audio Callback -----------------
def callback(indata, frames, time_info, status):
    q.put(bytes(indata))

# ----------------- Speech Recognition -----------------
model = Model(os.path.join(this_directory, "vosk-en-us"))
rec = KaldiRecognizer(model, 16000)

# ----------------- Command Handling -----------------
def handle_command(command_word, argument):
    if command_word == "go":
        node.send("voice/command", {"task":"navigation","location":argument}) # to match simple behaviour tree
        speak(f"going to {argument}")

    elif command_word == "stop":
        node.send("stop", True)
        speak("Stopping robot immediately")

    else:
        speak(f"Unknown command: {command_word}")
        

# ----------------- Handle speech -----------------

def handle_speak(data):
    text = data["text"]
    speak(text)
    
def handle_command_listen(data):
    global listenForCommand
    if data["action"]:
        listenForCommand = data["action"] == "listen"
    
    
node.subscribe("voice/speak",handle_speak)
node.subscribe("voice/command",handle_command_listen)


# ----------------- Main Loop -----------------
running = True

speak(f"Hello! my name is {TRIGGER_WORD}.")
print(f"🎤 Say '{TRIGGER_WORD} go to [place]' or '{TRIGGER_WORD} stop'")

with sd.RawInputStream(
    samplerate=16000,
    blocksize=4000,
    dtype='int16',
    channels=1,
    callback=callback
):
    while running:
        data = q.get()

        if rec.AcceptWaveform(data):
            result = json.loads(rec.Result())
            text = result["text"].lower().strip()

            if not text:
                continue

            # 🔍 Verbose debug output
            if VERBOSE:
                print(f"[HEARD]: {text}")

            # Exit command
            if EXIT_WORD in text:
                speak("Shutting down...")
                node.emit("start_shutdown")
                running = False
                break

            words = text.split()

            # Trigger word logic
            if listenForCommand:
                if words[0] in TRIGGER_WORD_LIST:
                    if len(words) > 1:
                        command_word = words[1]
                        argument = " ".join(words[2:] if len(words) > 2 else [])
                        handle_command(command_word, argument)
                    else:
                        speak("Yes sir?")

                elif TRIGGER_WORD in text:
                    speak(f"Incomplete command. Say: {TRIGGER_WORD} [command] [argument]")
