import sounddevice as sd
import queue
import json
import os
import sys
import pyttsx3
from vosk import Model, KaldiRecognizer

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))) # add parent folder to paths
from Server.Node import Node
from ControllerSerial.CommandChar import CommandChar

node = Node("voice","http://192.168.1.4:5000")
this_directory = os.path.dirname(os.path.abspath(__file__))


q = queue.Queue()
def callback(indata, frames, time_info, status):
    q.put(bytes(indata))

model = Model(os.path.join(this_directory,"vosk-en-us"))
rec = KaldiRecognizer(model, 16000)

TRIGGER_WORD = "vector"
TRIGGER_WORD_LIST = ["vector","victor","viktor","vicktor","victa","vitker"]   
EXIT_WORD = "thank you"   
running = True
print(f"🎤 Say '{TRIGGER_WORD} go to [place]' or '{TRIGGER_WORD} stop'")


def speak(voice):
    print(voice)
    engine = pyttsx3.init()
    engine.say(voice)
    engine.runAndWait()


def handle_command(command_word, argument):
    if command_word == "go":
        node.send("move_to",argument)
        voice = f"going to {argument}"
        speak(voice)
    elif command_word == "stop":
        node.send("stop",True)
        voice = "Stopping robot immediately"
        speak(voice)
    elif command_word == "spin":
        node.send("write_command",[CommandChar.APRIL_TAG_SEARCH])
        voice = "spinning right now"
        speak(voice)
    else:
        voice = f"Unknown command: {command_word}"
        speak(voice)


speak(f"Hello! my name is {TRIGGER_WORD}.")
    
    
with sd.RawInputStream(samplerate=16000, blocksize=4000, dtype='int16',
                channels=1, callback=callback):

    while running:
        data = q.get()
        if rec.AcceptWaveform(data):
            result = json.loads(rec.Result())
            text = result["text"].lower().strip()

            if not text:
                continue

            if EXIT_WORD in text:
                speak("Shutting down...")
                node.emit("start_shutdown")
                running = False
                break

            words = text.split()

            if words[0] in TRIGGER_WORD_LIST:
                if len(words) > 1:
                    command_word = words[1]
                    argument = " ".join(words[2:] if len(words) > 2 else [])
                    handle_command(command_word, argument)
                else:
                    speak("Yes sir?")
            # elif len(words) >= 2 and words[0] == TRIGGER_WORD and words[1] == "stop":
            #     stop_command()
            elif TRIGGER_WORD in text:
                speak(f"Incomplete command. Say: {TRIGGER_WORD} [command] [argument]")
