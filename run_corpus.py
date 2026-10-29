"""Throwaway experiment: run the "clip that" detector over a folder of wavs.

    python run_corpus.py corpus/          # restricted grammar (clip that / [unk])
    python run_corpus.py corpus/ full     # full vocabulary, no grammar

Prints, per file, every moment the recognizer heard one of the words we care
about (with confidence and how long the word lasted), and whether that counted
as a TRIGGER. Expects 48kHz stereo 16-bit wavs (what /dump gives you).
"""
import json
import sys
import wave
from pathlib import Path

from vosk import Model, KaldiRecognizer

from trigger import MODEL_PATH, to_16k_mono, find_trigger

STEP = 640  # 20ms of 16kHz 16-bit mono

# words worth printing in "full" mode (the phrase itself plus its look-alikes)
INTERESTING = {"clip", "clipped", "click", "clap", "flip", "quit", "skip", "that"}


def make_recognizer(model: Model, full: bool) -> KaldiRecognizer:
    if full:
        rec = KaldiRecognizer(model, 16000)
    else:
        rec = KaldiRecognizer(model, 16000, '["clip that", "[unk]"]')
    rec.SetWords(True)
    return rec


def describe(result: dict, full: bool) -> str | None:
    """One line about what the recognizer heard, or None if nothing interesting."""
    if full:
        keep = lambda word: word in INTERESTING
    else:
        keep = lambda word: word != "[unk]"

    heard = [
        f"{w['word']}@{w.get('conf', 0.0):.2f}({w['end'] - w['start']:.2f}s)"
        for w in result.get("result", [])
        if keep(w["word"])
    ]
    if not heard:
        return None

    trigger_time = find_trigger(result)
    label = f"TRIGGER at {trigger_time:.1f}s" if trigger_time is not None else "almost (no trigger)"
    line = f"{label}: {' '.join(heard)}"
    if full:
        line += f'   | heard: "{result.get("text", "")}"'
    return line


def detect(model: Model, path: Path, full: bool) -> tuple[list[str], int]:
    """Returns (lines about what it heard, number of triggers)."""
    rec = make_recognizer(model, full)

    with wave.open(str(path), "rb") as w:
        assert w.getframerate() == 48000 and w.getnchannels() == 2, f"{path}: need 48kHz stereo"
        pcm = w.readframes(w.getnframes())

    mono = to_16k_mono(pcm)

    results = []
    for i in range(0, len(mono), STEP):
        if rec.AcceptWaveform(mono[i:i + STEP]):
            results.append(json.loads(rec.Result()))
    results.append(json.loads(rec.FinalResult()))

    lines = []
    triggers = 0
    for result in results:
        line = describe(result, full)
        if line:
            lines.append(line)
            if line.startswith("TRIGGER"):
                triggers += 1

    return lines, triggers


def main(folder: str, mode: str = "grammar"):
    full = mode == "full"
    model = Model(MODEL_PATH)
    total = 0

    print(f"MODE: {'full vocabulary' if full else 'restricted grammar'}")
    for path in sorted(Path(folder).glob("*.wav")):
        lines, triggers = detect(model, path, full)
        total += triggers
        print(f"\n{path.name}: {triggers} trigger(s)")
        for line in lines:
            print("   ", line)

    print(f"\nTOTAL triggers across all files: {total}")


if __name__ == "__main__":
    main(*sys.argv[1:])