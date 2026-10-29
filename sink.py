from discord.ext import voice_recv

from buffers import UserBuffers


class ClipSink(voice_recv.AudioSink):
    """ Receives every voice packet. Only audio from opted-in people is kept. """

    def __init__(self, buffers: UserBuffers, opted_in: set[int], speech=None):
        super().__init__()
        self.buffers = buffers
        self.opted_in = opted_in  # shared with the session; consent changes show up live
        self.speech = speech      # SpeechWorkers (or None to just buffer)

    def wants_opus(self):
        return False

    def write(self, user, data: voice_recv.VoiceData):
        # Consent check first: nothing else happens for people who haven't opted in
        if user is None or user.id not in self.opted_in:
            return

        packet = data.packet
        rtp_timestamp = getattr(packet, "timestamp", None)
        ssrc = getattr(packet, "ssrc", None)

        if rtp_timestamp is None or ssrc is None:
            return

        self.buffers.add(user.id, data.pcm, rtp_timestamp, ssrc)

        if self.speech is not None:
            self.speech.feed(user.id, data.pcm)

    def cleanup(self):
        pass