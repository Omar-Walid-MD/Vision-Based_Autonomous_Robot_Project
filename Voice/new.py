#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║  vector — Unified Voice Assistant                           ║
║  Single-file implementation                                 ║
║  STT: Vosk (offline) | TTS: Piper (offline)                ║
╚══════════════════════════════════════════════════════════════╝

Usage:
    python vector.py                    # default settings
    python vector.py -v                 # verbose (show all speech)
    python vector.py --device 2         # force mic device ID
    python vector.py --voice en_GB-northern_english_male-medium

Install (Raspberry Pi):
    sudo apt install -y python3-pip portaudio19-dev espeak-ng
    pip3 install piper-tts vosk sounddevice numpy --break-system-packages
"""

from __future__ import annotations

import argparse
import audioop
import json
import os
import queue
import sys
import threading
import time
import wave
from pathlib import Path
from typing import Optional

import numpy as np
import sounddevice as sd

# ══════════════════════════════════════════════════════════════════
#  1. CONFIGURATION
# ══════════════════════════════════════════════════════════════════

SCRIPT_DIR = Path(__file__).parent.resolve()
PARENT_DIR = SCRIPT_DIR.parent.resolve()

# Allow importing the shared Node messaging client from ../Server
sys.path.append(str(PARENT_DIR))
from Server.Node import Node

# Paths — adjust these if your folders are elsewhere
VOSK_MODEL_PATH = SCRIPT_DIR / "vosk-en-us"
VOICES_DIR      = SCRIPT_DIR / "voices"
AUDIO_OUTPUT    = SCRIPT_DIR / "audio_output"
WORDS_FILE      = SCRIPT_DIR / "words.json"

# Node messaging
NODE_NAME       = "voice"
NODE_SERVER_URL = "http://localhost:5000"

# Audio / Microphone
SAMPLE_RATE   = 16000
BLOCKSIZE     = 4000
MIC_DEVICE    = 1          # Microphone (Realtek) — change via --device
VOSK_RATE     = 16000

# TTS
VOICE_MODEL        = "en_GB-northern_english_male-medium"
TTS_LENGTH_SCALE   = 0.85    # faster speech (lower = faster)
TTS_NOISE_SCALE    = 0.333   # lower = faster synthesis
TTS_NOISE_W_SCALE  = 0.5     # lower = faster synthesis

# How long (seconds) to keep ignoring the mic after TTS finishes speaking,
# to avoid the recognizer picking up the tail end of vector's own voice.
MIC_MUTE_COOLDOWN_SEC = 0.4


# ══════════════════════════════════════════════════════════════════
#  1b. VOICE COMMAND / WAKE WORD DATA (loaded from words.json)
# ══════════════════════════════════════════════════════════════════

def load_word_data(path: Path) -> dict:
    """Load wake words, command synonyms, response synonyms, and exit phrases
    from a JSON file and reshape them into the lookup structures used below.
    """
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    wake_words: list[str] = raw["WAKE_WORDS"]

    # Map every synonym phrase -> its canonical command name
    command_synonyms: dict[str, str] = {}
    command_groups = {
        "go":     raw.get("GO_COMMAND", []),
        "stop":   raw.get("STOP_COMMAND", []),
        "spin":   raw.get("SPIN_COMMAND", []),
        "status": raw.get("STATUS_COMMAND", []),
    }
    for canonical, synonyms in command_groups.items():
        for syn in synonyms:
            command_synonyms[syn] = canonical

    # Map every yes/no synonym -> "yes" or "no"
    response_synonyms: dict[str, str] = {}
    for syn in raw.get("YES_RESPONSE", []):
        response_synonyms[syn] = "yes"
    for syn in raw.get("NO_RESPONSE", []):
        response_synonyms[syn] = "no"

    exit_phrases: list[str] = raw.get("EXIT_PHRASES", [])

    return {
        "WAKE_WORDS": wake_words,
        "COMMAND_SYNONYMS": command_synonyms,
        "RESPONSE_SYNONYMS": response_synonyms,
        "EXIT_PHRASES": exit_phrases,
    }


_word_data = load_word_data(WORDS_FILE)

WAKE_WORDS: list[str]          = _word_data["WAKE_WORDS"]
COMMAND_SYNONYMS: dict[str, str] = _word_data["COMMAND_SYNONYMS"]
RESPONSE_SYNONYMS: dict[str, str] = _word_data["RESPONSE_SYNONYMS"]
EXIT_PHRASES: list[str]        = _word_data["EXIT_PHRASES"]


# ══════════════════════════════════════════════════════════════════
#  2. WAKE WORD & EXIT DETECTION
# ══════════════════════════════════════════════════════════════════

def is_wake_word(text: str) -> bool:
    words = text.lower().split()
    return any(w in WAKE_WORDS for w in words)

def extract_command_after_wake(text: str) -> Optional[str]:
    words = text.lower().split()
    for i, word in enumerate(words):
        if word in WAKE_WORDS:
            rest = " ".join(words[i + 1:]).strip()
            return rest if rest else None
    return None

def is_exit_phrase(text: str) -> bool:
    t = text.lower()
    return any(p in t for p in EXIT_PHRASES)


# ══════════════════════════════════════════════════════════════════
#  3. PIPER TTS ENGINE
# ══════════════════════════════════════════════════════════════════

class PiperTTSEngine:
    """Wrapper around the piper-tts library."""

    def __init__(self, voice_model: str, voices_dir: Path):
        self._voice_model = voice_model
        self._voice = None
        self._voices_dir = Path(voices_dir)
        self._model_path = self._voices_dir / f"{voice_model}.onnx"
        self._config_path = self._voices_dir / f"{voice_model}.onnx.json"

    def load_model(self) -> None:
        from piper import PiperVoice
        if not self._model_path.exists():
            raise FileNotFoundError(f"Voice model not found: {self._model_path}")
        print(f"Loading voice model: {self._voice_model}...")
        t0 = time.time()
        self._voice = PiperVoice.load(str(self._model_path), config_path=str(self._config_path))
        print(f"Voice model loaded in {time.time() - t0:.2f}s")

    def synthesize_to_bytes(self, text: str, length_scale=1.0, noise_scale=0.667, noise_w_scale=0.8) -> tuple:
        from piper import SynthesisConfig
        voice = self._voice
        cfg = SynthesisConfig(length_scale=length_scale, noise_scale=noise_scale, noise_w_scale=noise_w_scale)
        chunks = []
        sr = sw = ch = None
        for chunk in voice.synthesize(text, syn_config=cfg):
            if sr is None:
                sr, sw, ch = chunk.sample_rate, chunk.sample_width, chunk.sample_channels
            chunks.append(chunk.audio_int16_bytes)
        return b"".join(chunks), sr, sw, ch


# ══════════════════════════════════════════════════════════════════
#  4. TTS ENGINE (threaded wrapper)
# ══════════════════════════════════════════════════════════════════

class TTSEngine:
    """Non-blocking Piper TTS with background playback."""

    def __init__(self, voice_model: str, voices_dir: Path):
        self._engine = PiperTTSEngine(voice_model, voices_dir)
        self.is_speaking = False
        self.last_finished_at = 0.0
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._engine.load_model()

    def stop(self) -> None:
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def speak(self, text: str, callback=None) -> None:
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._thread = threading.Thread(target=self._play, args=(text, callback), daemon=True)
        self._thread.start()

    def speak_sync(self, text: str) -> None:
        self._play(text, callback=None)

    def should_mute_mic(self) -> bool:
        """True while vector is speaking, or briefly after, so its own
        voice isn't picked up and transcribed by the recognizer."""
        with self._lock:
            if self.is_speaking:
                return True
            return (time.time() - self.last_finished_at) < MIC_MUTE_COOLDOWN_SEC

    def _play(self, text: str, callback) -> None:
        with self._lock:
            self.is_speaking = True
        try:
            print(f"\U0001f50a [vector]: {text}")
            audio_bytes, sr, _sw, ch = self._engine.synthesize_to_bytes(
                text, length_scale=TTS_LENGTH_SCALE,
                noise_scale=TTS_NOISE_SCALE, noise_w_scale=TTS_NOISE_W_SCALE,
            )
            arr = np.frombuffer(audio_bytes, dtype=np.int16)
            if ch > 1:
                arr = arr.reshape(-1, ch)
            sd.play(arr, samplerate=sr)
            sd.wait()
        except Exception as e:
            print(f"[TTS] Error: {e}")
        finally:
            with self._lock:
                self.is_speaking = False
                self.last_finished_at = time.time()
            if callback:
                callback()


# ══════════════════════════════════════════════════════════════════
#  5. COMMAND REGISTRY
# ══════════════════════════════════════════════════════════════════

class CommandRegistry:
    """Synonym-aware command dispatch."""

    def __init__(self) -> None:
        self._handlers: dict[str, dict] = {}

    def register(self, canonical: str, handler, requires_arg: bool = False) -> None:
        self._handlers[canonical] = {"handler": handler, "requires_arg": requires_arg}

    def dispatch(self, command_text: str, assistant: "VectorVoiceAssistant") -> bool:
        text = command_text.strip().lower()
        if not text:
            return False
        for synonym in sorted(COMMAND_SYNONYMS.keys(), key=len, reverse=True):
            # Match the synonym only on a word boundary, so "go" doesn't
            # accidentally match inside "going to the kitchen".
            if text == synonym or text.startswith(synonym + " "):
                canonical = COMMAND_SYNONYMS[synonym]
                spec = self._handlers.get(canonical)
                if spec is None:
                    continue
                arg = text[len(synonym):].strip()
                for prep in ("to ", "at ", "the ", "my "):
                    if arg.startswith(prep):
                        arg = arg[len(prep):]
                if spec["requires_arg"] and not arg:
                    assistant.speak(f"Where should I {canonical}?")
                    return True
                spec["handler"](arg)
                return True
        assistant.speak(f"Sorry, I don't understand: {command_text}")
        return False

    def list_commands(self) -> list[str]:
        return list(self._handlers.keys())


# ══════════════════════════════════════════════════════════════════
#  6. MAIN ASSISTANT CLASS
# ══════════════════════════════════════════════════════════════════

STATE_IDLE    = "idle"
STATE_MOVING  = "moving"
STATE_ASKING  = "asking"


class VectorVoiceAssistant:
    """Unified, standalone voice assistant."""

    def __init__(self, verbose=False, mic_device=None, voice_model=VOICE_MODEL, tts_only=False):
        self.verbose = verbose
        self.mic_device = mic_device if mic_device is not None else MIC_DEVICE
        self.voice_model = voice_model
        self.tts_only = tts_only

        self.tts = TTSEngine(voice_model, VOICES_DIR)
        self.commands = CommandRegistry()

        self.state = STATE_IDLE
        self._move_start = 0.0
        self.running = False

        # When False, the "go" command is ignored (e.g. while already
        # moving, or while some other operation has it locked out).
        self.go_enabled = True

        # Register command handlers
        self.commands.register("go",        self.handle_go,        requires_arg=True)
        self.commands.register("stop",      self.handle_stop)
        self.commands.register("spin",      self.handle_spin)
        self.commands.register("status",    self.handle_status)

        # ── Node messaging ──────────────────────────────────────────
        self.node = Node(NODE_NAME, NODE_SERVER_URL)
        self.node.subscribe("voice/speak", self.handle_speak_event)
        self.node.subscribe("voice/command", self.handle_command_listen_event)

    # ── Node event handlers ───────────────────────────────────────────

    def handle_speak_event(self, data: dict) -> None:
        """Speak text that was sent to us from elsewhere on the network."""
        text = data.get("text")
        if text:
            self.speak(text)

    def handle_command_listen_event(self, data: dict) -> None:
        """Enable/disable the 'go' command based on an external signal,
        mirroring the old `listenForCommand` toggle."""
        action = data.get("action")
        if action:
            self.go_enabled = (action == "listen")

    # ── Run ────────────────────────────────────────────────────────

    def run(self) -> None:
        self.running = True

        if self.tts_only:
            self._run_tts_only()
            return

        from vosk import Model, KaldiRecognizer

        # ── Load TTS and STT models in parallel ────────────────────
        print("[Startup] Loading models in parallel...")
        t0 = time.time()
        vosk_result: dict = {}

        def _load_vosk():
            vosk_result["model"] = Model(str(VOSK_MODEL_PATH))

        vosk_thread = threading.Thread(target=_load_vosk, daemon=True)
        vosk_thread.start()

        self.tts.start()           # loads Piper on main thread

        vosk_thread.join()         # wait for Vosk if not done yet
        model = vosk_result["model"]
        print(f"[Startup] All models loaded in {time.time() - t0:.2f}s")

        rec = KaldiRecognizer(model, VOSK_RATE)

        # ── Greet while opening mic (non-blocking) ─────────────────
        self.tts.speak("Hello! My name is vector. I am ready for your commands.")
        # Wait for greeting to finish before listening
        while self.tts.is_speaking:
            time.sleep(0.1)
        cmds = ", ".join(self.commands.list_commands())
        print(f"\U0001f3a4 Say 'vector [command]'. Available: {cmds}")
        print("  Say 'goodbye' to shut down.\n")

        # Many devices (especially over raw ALSA) refuse to capture at
        # 16000 Hz directly. Open the stream at the device's native rate
        # and resample each chunk down to VOSK_RATE (16 kHz) instead.
        device_info = sd.query_devices(self.mic_device, "input")
        device_rate = int(device_info["default_samplerate"])
        needs_resample = device_rate != VOSK_RATE
        if needs_resample:
            print(f"[STT] Mic native rate is {device_rate} Hz — resampling to {VOSK_RATE} Hz")
        device_blocksize = int(BLOCKSIZE * device_rate / VOSK_RATE)

        q: queue.Queue[bytes] = queue.Queue()
        resample_state = None

        def cb(indata, frames, time_info, status):
            nonlocal resample_state
            data = bytes(indata)
            if needs_resample:
                data, resample_state = audioop.ratecv(
                    data, 2, 1, device_rate, VOSK_RATE, resample_state
                )
            q.put(data)

        print(f"[STT] Opening mic (device {self.mic_device})...")
        try:
            with sd.RawInputStream(
                samplerate=device_rate, blocksize=device_blocksize,
                dtype="int16", channels=1, callback=cb, device=self.mic_device,
            ):
                print("[STT] Listening — say 'vector [command]'...\n")
                while self.running:
                    try:
                        data = q.get(timeout=0.2)
                    except queue.Empty:
                        continue

                    if self.tts.should_mute_mic():
                        # Discard audio captured while vector is talking
                        # (or just finished) so it doesn't transcribe itself.
                        continue

                    if rec.AcceptWaveform(data):
                        result = json.loads(rec.Result())
                        text = result.get("text", "").strip()
                        if not text or not self._valid_transcript(text):
                            continue
                        text = text.lower()
                        if self.verbose:
                            print(f"\U0001f5e3\ufe0f  [YOU]: {text}")
                        if is_exit_phrase(text):
                            self.running = False
                            break
                        if self.state == STATE_IDLE:
                            self._handle_idle(text)
                        elif self.state == STATE_ASKING:
                            self._handle_asking(text)
        except KeyboardInterrupt:
            print("\n[vector] Interrupted.")
        except Exception as e:
            print(f"[vector] Error: {e}")
        finally:
            self.shutdown()

    def _run_tts_only(self) -> None:
        """Load only the TTS engine and let you type lines for it to speak.
        No microphone or Vosk model is needed — useful for testing voices
        on a machine with no mic connected."""
        print("[Startup] Loading TTS model...")
        t0 = time.time()
        self.tts.start()
        print(f"[Startup] TTS loaded in {time.time() - t0:.2f}s")

        self.tts.speak_sync("Hello! This is a text to speech test. Type a line and press enter to hear it. Type exit to quit.")
        print("\n[TTS-only] Type text and press Enter to have vector speak it.")
        print("           Type 'exit' or 'quit' to stop.\n")

        try:
            while self.running:
                try:
                    line = input("> ").strip()
                except EOFError:
                    break
                if not line:
                    continue
                if line.lower() in ("exit", "quit"):
                    break
                self.tts.speak_sync(line)
        except KeyboardInterrupt:
            print("\n[vector] Interrupted.")
        finally:
            self.shutdown()

    # ── Speech ─────────────────────────────────────────────────────

    def speak(self, text: str) -> None:
        self.tts.speak(text)

    def speak_sync(self, text: str) -> None:
        self.tts.speak_sync(text)

    # ── Command Handlers ───────────────────────────────────────────

    def handle_go(self, argument: str) -> None:
        if not self.go_enabled:
            self.speak("I can't go right now.")
            return
        self.state = STATE_MOVING
        self._move_start = time.time()
        self.go_enabled = False
        self.node.send("voice/command", {"task": "navigation", "location": argument})
        self.speak(f"Going to {argument} right now.")

    def handle_stop(self, _arg: str = "") -> None:
        print("[CMD] stop")
        self.speak("Stopping immediately.")
        self.state = STATE_IDLE
        self.go_enabled = True

    def handle_spin(self, _arg: str = "") -> None:
        print("[CMD] spin")
        self.speak("Spinning right now.")

    def handle_status(self, _arg: str = "") -> None:
        msgs = {
            STATE_IDLE:   "I am idle and waiting for your commands. I am ready.",
            STATE_MOVING: "I am currently moving to the destination. Please wait.",
            STATE_ASKING: "I have arrived. Please tell me if you are okay.",
        }
        self.speak(msgs.get(self.state, "I am in an unknown state."))

    # ── State Machine ──────────────────────────────────────────────

    def _handle_idle(self, text: str) -> None:
        if not is_wake_word(text):
            return
        cmd = extract_command_after_wake(text)
        if cmd:
            self.commands.dispatch(cmd, self)
        else:
            self.speak("Yes sir?")

    def _handle_asking(self, text: str) -> None:
        words = text.lower().split()
        response = None
        for w in words:
            if w in RESPONSE_SYNONYMS:
                response = RESPONSE_SYNONYMS[w]
                break
        if response == "yes":
            self.speak("Glad to hear that. I will return to base now.")
            self.state = STATE_IDLE
            self.go_enabled = True
        elif response == "no":
            self.speak("I am sorry. I am calling for help immediately.")
            print("[CMD] call_help")
            self.state = STATE_IDLE
            self.go_enabled = True
        else:
            self.speak("Please answer with yes or no.")

    # ── Helpers ────────────────────────────────────────────────────

    @staticmethod
    def _valid_transcript(text: str) -> bool:
        words = text.split()
        if all(w == "the" for w in words):
            return False
        if len(words) == 1:
            allowed = set(WAKE_WORDS) | set(RESPONSE_SYNONYMS.keys())
            if words[0] not in allowed:
                return False
        return True

    def shutdown(self) -> None:
        if not self.running:
            return
        self.running = False
        self.speak_sync("Shutting down. Goodbye.")
        print("[vector] System shut down.")


# ══════════════════════════════════════════════════════════════════
#  7. ENTRY POINT
# ══════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(description="vector — Unified Voice Assistant")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show all detected speech")
    parser.add_argument("--device", type=int, default=None, help="Microphone device ID")
    parser.add_argument("--voice", type=str, default=VOICE_MODEL, help="Piper voice model name")
    parser.add_argument("--tts-only", action="store_true",
                         help="Skip the mic/Vosk entirely; type lines to have vector speak them")
    args = parser.parse_args()

    assistant = VectorVoiceAssistant(
        verbose=args.verbose,
        mic_device=args.device,
        voice_model=args.voice,
        tts_only=args.tts_only,
    )
    assistant.run()


if __name__ == "__main__":
    main()