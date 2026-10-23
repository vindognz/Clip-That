SAMPLE_RATE = 48000
BYTES_PER_FRAME = 4 # 2 channels x 2 bytes
BYTES_PER_SECOND = SAMPLE_RATE * BYTES_PER_FRAME

PAUSE_TOLERANCE_SECONDS = 0.1 # TWEAK

def render_track(entries: list, window_start: float, seconds: float) -> bytes:
    """ entries: list of (monotonic_timestamp, pcm_chunk) tuples
        Returns `seconds` of audio with silence where nobody spoke.
    """

    num_bytes = int(BYTES_PER_SECOND * seconds)
    size = int((num_bytes // BYTES_PER_FRAME) * BYTES_PER_FRAME)
    track = bytearray(size)

    tolerance = int(BYTES_PER_SECOND * PAUSE_TOLERANCE_SECONDS)
    cursor = None

    for timestamp, chunk in entries:
        seconds_in = timestamp - window_start

        initial_offset = seconds_in * BYTES_PER_SECOND
        initial_offset = int((initial_offset // BYTES_PER_FRAME) * BYTES_PER_FRAME)

        if cursor is None or initial_offset - cursor > tolerance:
            position = initial_offset
        else:
            position = cursor

        end = position + len(chunk)

        if position < 0 or end > len(track):
            continue

        track[position:end] = chunk

        cursor = end

    return bytes(track)

def render_track_rtp(entries: list, window_start: float, seconds: float) -> bytes:
    """ entries: list of (arrival_time, rtp_timestamp, ssrc, pcm_chunk)
    """

    num_bytes = int(BYTES_PER_SECOND * seconds)
    size = int((num_bytes // BYTES_PER_FRAME) * BYTES_PER_FRAME)
    track = bytearray(size)

    if not entries:
        return bytes(track)

    unwrapped = []
    total = 0
    prev = entries[0][1]

    for _, rtp_timestamp, _, _ in entries:
        delta = (rtp_timestamp - prev) & 0xFFFFFFFF

        if delta >= 2**31:
            delta -= 2**32

        total += delta
        unwrapped.append(total)

        prev = rtp_timestamp

    anchor = min(arrival - u / SAMPLE_RATE for (arrival, _, _, _), u in zip(entries, unwrapped))
    anchor_frames = round((anchor - window_start) * SAMPLE_RATE)

    for (_, _, _, chunk), u in zip(entries, unwrapped):
        position = (anchor_frames + u) * BYTES_PER_FRAME

        end = position + len(chunk)

        if position < 0 or end > len(track):
            continue

        track[position:end] = chunk

    return bytes(track)