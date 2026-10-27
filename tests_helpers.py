# an entry is (arrival_time, rtp_timestamp, ssrc, pcm_chunk)
CHUNK = b"\x01" * 3840 # 20ms of fake audio
START = 1000.0         # window_start for tests
RTP_STEP = 960         # one 20ms packet = 960 samples at 48kHz
BASE = 5000            # random starting RTP timestamp

def pkt(arrival, rtp, ssrc=1, chunk=CHUNK):
    return (arrival, rtp, ssrc, chunk)