import time
from collections import deque, defaultdict

class UserBuffers:
    def __init__(self, seconds: float):
        self.seconds = seconds
        self.buffer = defaultdict(deque) # user_id -> deque

    def add(self, user_id: int, pcm: bytes):
        user_deque: deque = self.buffer[user_id]
        now = time.monotonic()

        user_deque.append((now, pcm))

        # prune old entries
        cutoff = now - self.seconds

        while user_deque and user_deque[0][0] < cutoff:
            user_deque.popleft()

    def clear(self, user_id: int):
        # remove this user's audio entirely
        self.buffer.pop(user_id, None)
