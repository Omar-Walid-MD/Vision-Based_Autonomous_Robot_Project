import os
import subprocess
# ~ import pyttsx3
from dotenv import load_dotenv
load_dotenv()
platform = os.getenv("PLATFORM")

VOICE = "mb-en1"
SPEED = str(100)

def speak(text):
	print(text)
	if platform == "RPI":
		subprocess.run(["espeak", "-v", VOICE, "-s", SPEED, text])

	else:
		engine = pyttsx3.init()
		engine.say(text)
		engine.runAndWait()
		
if __name__ == "__main__":
	while True:
		text = input("Enter text to speak (or 'exit'): ")
		if text.lower() == "x":
			break
		speak(text)
