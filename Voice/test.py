import sounddevice as sd
import queue
import json
import os
import pyttsx3
from vosk import Model, KaldiRecognizer

this_directory = os.path.dirname(os.path.abspath(__file__))

# إعداد الطابور علشان الصوت
q = queue.Queue()

def callback(indata, frames, time, status):
    q.put(bytes(indata))

# تحميل الموديل (تأكد إن اسم الفولدر هو نفس الاسم عندك)

model = Model(os.path.join(this_directory,"vosk-en-us"))
rec = KaldiRecognizer(model, 16000)

# إعداد TTS
engine = pyttsx3.init()
engine.setProperty("rate", 150)  # سرعة الصوت
engine.setProperty("volume", 1.0)  # مستوى الصوت

def speak(text):
    engine.say(text)
    engine.runAndWait()

# إعداد المايك
with sd.RawInputStream(samplerate=16000, blocksize=8000, dtype="int16",
                       channels=1, callback=callback):
    print("🎤 Speak now... (Ctrl+C to stop)")

    while True:
        data = q.get()
        if rec.AcceptWaveform(data):
            result = json.loads(rec.Result())
            text = result["text"]
            if text.strip():
                print("You said:", text)

                # رد بسيط كمثال
                if "hello" in text:
                    reply = "Hello there! How are you?"
                elif "name" in text:
                    reply = "I am your Raspberry Pi assistant."
                elif "bye" in text:
                    reply = "Goodbye!"
                    speak(reply)
                    break
                else:
                    reply = "I heard you say " + text

                print("🤖:", reply)
                speak(reply)
