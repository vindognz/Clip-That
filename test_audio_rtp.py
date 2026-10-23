from audio import render_track_rtp, BYTES_PER_SECOND, BYTES_PER_FRAME

# an entry is (arrival_time, rtp_timestamp, ssrc, pcm_chunk)
CHUNK = b"\x01" * 3840 # 20ms of fake audio
START = 1000.0         # window_start for tests
RTP_STEP = 960         # one 20ms packet = 960 samples at 48kHz
BASE = 5000            # random starting RTP timestamp

def pkt(arrival, rtp, ssrc=1, chunk=CHUNK):
    return (arrival, rtp, ssrc, chunk)

def test_jitter_does_not_matter():
    entries = [
        pkt(START + 0.500, BASE + 0 * RTP_STEP),
        pkt(START + 0.522, BASE + 1 * RTP_STEP),
        pkt(START + 0.538, BASE + 2 * RTP_STEP)
    ]
    track = render_track_rtp(entries, START, 2)

    s = track.find(b"\x01") # where the first chunk starts
    assert abs(s - int(0.5 * BYTES_PER_SECOND)) < int(0.02 * BYTES_PER_SECOND)
    assert track[s:s + 3 * len(CHUNK)] == CHUNK * 3
    assert len(track) == 2 * BYTES_PER_SECOND

def test_pause_lands_in_the_right_place():
    entries = [
        pkt(START + 0.5, BASE),
        pkt(START + 1.5, BASE + 48000), # RTP jumped 1 second
    ]
    track = render_track_rtp(entries, START, 3)

    s1 = track.find(b"\x01")                   # start of chunk 1
    s2 = track.rfind(b"\x01") - len(CHUNK) + 1 # start of chunk 2

    assert abs(s1 - s2) == BYTES_PER_SECOND

def test_lost_packet_leaves_exactly_one_packets_of_silence():
    entries = [
        pkt(START + 0.50, BASE + 0 * RTP_STEP),
        pkt(START + 0.52, BASE + 1 * RTP_STEP),
        pkt(START + 0.56, BASE + 3 * RTP_STEP),
    ]
    track = render_track_rtp(entries, START, 2)

    s1 = track.find(b"\x01")
    n = len(CHUNK)

    assert track[s1 : s1 + 2*n] == CHUNK * 2 # chunks 1 and 2 are back to back
    assert track[s1 + 2*n : s1 + 3*n] == bytes(n)
    assert track[s1 + 3*n : s1 + 4*n] == CHUNK

def test_late_first_packet_does_not_shift_the_track():
    entries = [
        pkt(START + 0.58, BASE),                # 80ms late
        pkt(START + 0.52, BASE + RTP_STEP),     # on time
        pkt(START + 0.54, BASE + 2 * RTP_STEP), # on time
    ]
    track = render_track_rtp(entries, START, 2)

    s = track.find(b"\x01")
    
    # s should be 0.5s into the track (+/- one frame)
    bytes_per_half_sec = 0.5 * BYTES_PER_SECOND
    assert bytes_per_half_sec - BYTES_PER_FRAME <= s <= bytes_per_half_sec + BYTES_PER_FRAME

    assert track[s : s + 3*len(CHUNK)] == CHUNK * 3

def test_timestamp_wraparound():
    entries = [
        pkt(START + 0.5 + i * 0.02, (2**32 - 1920 + i * RTP_STEP) % 2**32)
        for i in range(4)
    ]
    track = render_track_rtp(entries, START, 2)

    s = track.find(b"\x01")

    assert track[s : s + 4*len(CHUNK)] == CHUNK * 4


def test_empty_is_silence_of_the_right_length():
    # no entries -> exactly 2 seconds of zeros
    track = render_track_rtp([], START, 2)

    assert not any(track)
    assert len(track) == 2 * BYTES_PER_SECOND

def test_too_old_is_skipped():
    # one chunk that arrived a second before START -> all silence, length unchanged
    entries = [
        pkt(START - 1.0, BASE),
    ]
    track = render_track_rtp(entries, START, 2)

    assert not any(track)
    assert len(track) == 2 * BYTES_PER_SECOND

def test_past_the_end_is_skipped_and_length_stays_exact():
    # one chunk at START + 1.99 in a 2 second window -> skipped, length unchanged
    entries = [
        pkt(START + 1.99, BASE),
    ]
    track = render_track_rtp(entries, START, 2)

    assert len(track) == 2 * BYTES_PER_SECOND
