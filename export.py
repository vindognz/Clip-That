import numpy as np
import lameenc
import re
import zipfile
import io

def mix_tracks(tracks: list[bytes]) -> bytes:
    """ Mix equal-length 16-bit PCM tracks into one.
    """

    if not tracks:
        raise ValueError("No tracks")

    total = np.zeros(len(tracks[0]) // 2, dtype=np.int32)
    for track in tracks:
        total += np.frombuffer(track, dtype=np.int16)
    total = np.clip(total, -32768, 32767)

    return total.astype(np.int16).tobytes()

def pcm_to_mp3(pcm: bytes) -> bytes:
    """ Turns pcm bytes into mp3 bytes.
    """

    encoder = lameenc.Encoder()
    encoder.set_bit_rate(128)
    encoder.set_in_sample_rate(48000)
    encoder.set_channels(2)
    encoder.set_quality(2)

    out = encoder.encode(pcm) + encoder.flush()

    return bytes(out)

def safe_filename(name: str) -> str:
    """ Turns a Discord display name into something safe to use as a filename.
    """

    clean = re.sub(r"[^\w\- ]", "_", name)

    if not clean:
        return "track"

    return clean

def build_zip(files: dict[str, bytes]) -> bytes:
    """ files maps filename -> file bytes.
        Returns the zip file's bytes.
    """

    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_STORED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)

    return buffer.getvalue()