import numpy as np
import lameenc
import re
import zipfile
import io

from audio import render_track_rtp

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
    """ Turns a Discord username into something safe to use as a filename.
    """

    illegals_removed = re.sub(r"[^\w.\-]", "_", name)
    double_dot_collapsed = re.sub(r"\.{2,}", "_", illegals_removed)
    clean = double_dot_collapsed.strip('.')

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

def render_tracks(entries_by_user: dict[int, list], window_start: float, seconds: float) -> dict[int, bytes]:
    """ Render every user's audio onto the same timeline
        Entirely silent tracks are left out
    """

    tracks = {}

    for user_id, entries in entries_by_user.items():
        pcm = render_track_rtp(entries, window_start, seconds)

        if pcm != bytes(len(pcm)):
            tracks[user_id] = pcm

    return tracks

def build_clip(tracks: dict[int, bytes], names: dict[int, str]) -> tuple[bytes, bytes] | None:
    """ tracks: user_id -> rendered PCM (what render_tracks returns)
        names:  user_id -> username (a user who left may be missing)
        Returns (mixed_mp3, zip_bytes), or None if there's nothing to clip.
    """

    if not tracks:
        return None

    mixed = mix_tracks(list(tracks.values()))
    mixed_mp3 = pcm_to_mp3(mixed)

    to_zip = {}

    for user_id in tracks.keys():
        name = names.get(user_id, str(user_id))
        filename = safe_filename(name) + ".mp3"

        user_mp3 = pcm_to_mp3(tracks[user_id])
        to_zip[filename] = user_mp3

    zip_bytes = build_zip(to_zip)

    return mixed_mp3, zip_bytes