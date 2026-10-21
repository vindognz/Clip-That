from discord.ext import voice_recv
from buffers import UserBuffers

class ClipSink(voice_recv.AudioSink):
    def __init__(self, buffers: UserBuffers, opted_in: set[int]):
        super().__init__()
        self.buffers = buffers
        self.opted_in = opted_in

    def wants_opus(self):
        return False

    def write(self, user, data: voice_recv.VoiceData):
        if user is None or user.id not in self.opted_in:
            return

        self.buffers.add(user.id, data.pcm)

    def cleanup(self):
        pass