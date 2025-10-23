import os
import pyttsx3
from dotenv import load_dotenv
load_dotenv()
platform = os.getenv("PLATFORM")

def speak(text):
	print(text)
	if platform == "RPI":
		os.system(f'espeak-ng -v en+m7 -s 150 -p 75 "{text}"')
	else:
		engine = pyttsx3.init()
		engine.say(text)
		engine.runAndWait()