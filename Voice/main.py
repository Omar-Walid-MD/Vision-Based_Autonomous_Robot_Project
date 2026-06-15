import argparse
import json
import os
import subprocess
import sys
import threading
from dotenv import load_dotenv
import pyttsx3

# ----------------- Setup -----------------
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from Server.Node import Node

this_directory = os.path.dirname(os.path.abspath(__file__))

# Load environment
load_dotenv()
platform = os.getenv("PLATFORM")

# CLI arguments
parser = argparse.ArgumentParser()
parser.add_argument("-v", "--verbose", action="store_true", help="Show all entered text")
args = parser.parse_args()
VERBOSE = args.verbose

# Node
node = Node("voice", "http://localhost:5000")

# ----------------- Constants -----------------
TRIGGER_WORD = "vector"
TRIGGER_WORD_LIST = ["vector", "victor", "viktor", "vicktor", "victa", "vitker"]
EXIT_WORD = "thank you"

VOICE = "mb-en1"
SPEED = "100"

listenForCommand = False

# ----------------- TTS (Unified) -----------------
engine = None
if platform != "RPI":
    engine = pyttsx3.init()


def speak(text):
    print(f"[TTS]: {text}")

    if platform == "RPI":
        subprocess.run(["espeak", "-v", VOICE, "-s", SPEED, text])
    else:
        engine.say(text)
        engine.runAndWait()


# ----------------- Command Handling -----------------
def handle_command(command_word, argument):
    if command_word == "go":
        if argument.lower() == "charger":
            location = "charger"
        else:
            location = argument.upper()
        node.send("voice/command", {"task": {"task": "navigation", "location": location}})
        speak(f"going to {location}")

# ----------------- Handle speech / Node Events -----------------
def handle_speak(data):
    text = data["text"]
    speak(text)


def handle_command_listen(data):
    global listenForCommand
    # ✅ FIX: Only process messages that contain the 'action' key
    if "action" in data:
        listenForCommand = data["action"] == "listen"
    # Ignore other messages (e.g., navigation commands from CLI)


node.subscribe("voice/speak", handle_speak)
node.subscribe("voice/command", handle_command_listen)

# ----------------- Main Loop -----------------
running = True

speak(f"Hello! my name is {TRIGGER_WORD}.")
print(f"⌨️ Type '{TRIGGER_WORD} go to [place]' or '{TRIGGER_WORD} stop'")

try:
    while running:
        # Get input from the CLI instead of the mic
        text = input("\nEnter Command > ").lower().strip()

        if not text:
            continue

        # 🔍 Verbose debug output
        if VERBOSE:
            print(f"[INPUT]: {text}")

        # Exit command
        if EXIT_WORD in text:
            speak("Shutting down...")
            node.emit("start_shutdown")
            running = False
            break

        words = text.split()

        # Trigger word logic
        if words[0] in TRIGGER_WORD_LIST:
            if len(words) > 1:
                command_word = words[1]
                argument = " ".join(words[2:] if len(words) > 2 else [])
                handle_command(command_word, argument)
            else:
                speak("Yes sir?")
        elif TRIGGER_WORD in text:
            speak(
                f"Incomplete command. Say: {TRIGGER_WORD} [command] [argument]"
            )
        else:
            if VERBOSE:
                print(
                    f"Ignored. Text did not start with a trigger word (e.g., '{TRIGGER_WORD}')."
                )

except (KeyboardInterrupt, SystemExit):
    print("\nExiting...")