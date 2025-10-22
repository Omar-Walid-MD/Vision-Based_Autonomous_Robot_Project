import sounddevice as sd
import queue
import json
import os
from tts import speak
from vosk import Model, KaldiRecognizer
# from Node import Node

# node = Node("voice")
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

def handle_command(command_word, argument):
    if command_word == "go":
        voice = f"going to {argument}"
        speak(voice)
        # node.send("voice_command",{
        #     "command": "goto",
        #     "arg": argument
        # })
    elif command_word == "stop":
        voice = "Stopping robot immediately"
        speak(voice)
        # node.send("voice_command",{
        #     "command": "stop",
        #     "arg": None
        # })
    else:
        voice = f"Unknown command: {command_word}"
        speak(voice)

    

speak(f"Hello! my name is {TRIGGER_WORD}. I am here to help you get to your destination today!")
    
    
with sd.RawInputStream(samplerate=16000, blocksize=8000, dtype='int16',
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
                running = False
                break

            words = text.split()

            if words[0] in TRIGGER_WORD_LIST:
                if len(words) > 1:
                    command_word = words[1]
                    argument = " ".join(words[2:] if len(words) > 2 else [])
                    handle_command(command_word, argument)
                else:
                    speak("Yes, sir?")
            # elif len(words) >= 2 and words[0] == TRIGGER_WORD and words[1] == "stop":
            #     stop_command()
            elif TRIGGER_WORD in text:
                speak(f"Incomplete command. Say: {TRIGGER_WORD} [command] [argument]")
