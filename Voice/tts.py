import os

def speak(text):
	os.system(f'espeak-ng -v en+m7 -s 150 -p 75 "{text}"')
