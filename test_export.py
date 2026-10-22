import numpy as np

from export import *


def pcm(*samples) -> bytes:
    """ Build fake PCM from a list of 16-bit sample values.
    """
    return np.array(samples, dtype=np.int16).tobytes()

def samples(data: bytes) -> list:
    """ Read PCM bytes back as a list of 16-bit sample values.
    """
    return np.frombuffer(data, dtype=np.int16).tolist()

def test_mix_adds_samples():
    a = pcm(100, -200, 300, 400)
    b = pcm(1, 2, 3, 4)
    assert samples(mix_tracks([a, b])) == [101, -198, 303, 404]

def test_mix_clips_instead_of_wrapping():
    a = pcm(30000, -30000)
    b = pcm(30000, -30000)
    assert samples(mix_tracks([a, b])) == [32767, -32768]

def test_single_track_is_unchanged():
    a = pcm(1, 2, 3, 4)
    assert mix_tracks([a]) == a

def test_mixing_with_silence_gives_the_audio_back():
    a = pcm(5, 6, 7, 8)
    silence = bytes(len(a))
    assert mix_tracks([a, silence]) == a

def test_output_is_bytes_of_the_same_length():
    a = pcm(1, 2, 3, 4)
    b = pcm(5, 6, 7, 8)
    result = mix_tracks([a, b])
    assert isinstance(result, bytes)
    assert len(result) == len(a)

def test_mp3_size_check():
    mp3 = pcm_to_mp3(bytes(48000 * 4 * 30))
    expected = 480000

    assert expected*0.98 < len(mp3) < expected*1.02

def test_looks_like_mp3_check():
    mp3 = pcm_to_mp3(bytes(48000 * 4 * 30))

    assert mp3[0] == 0xff