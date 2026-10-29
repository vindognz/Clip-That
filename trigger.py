import json
from pathlib import Path

import numpy as np
from vosk import KaldiRecognizer, SetLogLevel

SetLogLevel(-1)

# Absolute, so it works no matter which folder the bot is started from
MODEL_PATH = str(Path(__file__).resolve().parent / "vosk-model-small-en-us-0.15")

# Discord stops sending packets while someone is silent, so Vosk never "hears"
# the pause that ends a sentence. When a speaker goes quiet we feed it this much
# silence ourselves, which makes it finish the sentence and report what it heard.
SILENCE_SECONDS = 1.5
SILENCE_PACKET = bytes(640)  # 20ms of 16kHz 16-bit mono silence


def to_16k_mono(pcm: bytes) -> bytes:
    """ In:  48kHz stereo 16-bit PCM
        Out: 16kHz mono 16-bit PCM
    """

    samples = np.frombuffer(pcm, dtype=np.int16)
    stereo = samples.reshape(-1, 2)
    mono = (stereo[:, 0].astype(np.int32) + stereo[:, 1]) // 2

    n = len(mono) // 3 * 3 # trim to a multiple of 3
    down = mono[:n].reshape(-1, 3).mean(axis=1)

    return down.astype(np.int16).tobytes()


def find_trigger(result: dict, min_conf: float = 0.8) -> float | None:
    """ result: what json.loads(rec.Result()) gives you.
        Returns the time (seconds) the phrase ended, or None if "clip that" wasn't said.
    """
    words = result.get("result", [])

    for first, second in (zip(words, words[1:])):
        if first["word"] == "clip" and first.get("conf", 0.0) >= min_conf and second["word"] == "that" and second.get("conf", 0.0) >= min_conf:
            return second["end"]

    return None


class TriggerDetector:
    """ One speaker's recognizer (full vocabulary).
        Only ever use it from ONE thread.
    """

    def __init__(self, model=None, recognizer=None):
        if recognizer is None:
            recognizer = KaldiRecognizer(model, 16000)
            recognizer.SetWords(True)

        self.rec = recognizer
        self.dirty = False  # True = we've fed speech that hasn't been finished off yet

    def _accept(self, mono: bytes, real_audio: bool) -> bool:
        if self.rec.AcceptWaveform(mono):
            self.dirty = False
            return find_trigger(json.loads(self.rec.Result())) is not None

        if real_audio:
            self.dirty = True
        return False

    def feed(self, pcm: bytes) -> bool:
        """ pcm: one packet of 48kHz stereo 16-bit audio.
            Returns True if "clip that" was just recognised.
        """
        return self._accept(to_16k_mono(pcm), real_audio=True)

    def flush(self) -> bool:
        """ Call when the speaker has gone quiet. Feeds silence so Vosk finishes
            the sentence. Returns True if "clip that" was recognised.
        """
        if not self.dirty:
            return False

        for _ in range(int(SILENCE_SECONDS / 0.02)):
            if self._accept(SILENCE_PACKET, real_audio=False):
                self.dirty = False
                return True

        self.dirty = False
        return False