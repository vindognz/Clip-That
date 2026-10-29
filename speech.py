""" Runs speech recognition for each speaker on its own thread, so the voice
    thread (ClipSink.write) never waits on Vosk.
"""
import logging
import queue
import threading
import time

log = logging.getLogger(__name__)


class SpeechWorkers:
    """ One worker thread (and one detector) per speaker.

        make_detector(): returns an object with feed(pcm) -> bool and flush() -> bool
        on_trigger(user_id): called FROM A WORKER THREAD when someone says the phrase
        is_allowed(user_id): checked before a speaker's worker is created
        cooldown: seconds after a trigger during which other triggers are ignored
    """

    def __init__(self, make_detector, on_trigger, is_allowed=lambda user_id: True,
                 cooldown: float = 10.0, queue_size: int = 250, idle_seconds: float = 0.4):
        self._make_detector = make_detector
        self._on_trigger = on_trigger
        self._is_allowed = is_allowed
        self._cooldown = cooldown
        self._queue_size = queue_size
        self._idle_seconds = idle_seconds

        self._workers = {}  # user_id -> (queue, stop event)
        self._lock = threading.Lock()
        self._closed = False
        self._last_fire = float("-inf")

    def feed(self, user_id: int, pcm: bytes):
        """ Never blocks. If the speaker's queue is full, the packet is dropped. 
        """
        q = self._queue_for(user_id)
        if q is None:
            return

        try:
            q.put_nowait(pcm)
        except queue.Full:
            pass

    def remove(self, user_id: int):
        """ Stop listening to one speaker (e.g. they opted out).
        """
        with self._lock:
            worker = self._workers.pop(user_id, None)

        if worker is not None:
            worker[1].set()

    def close(self):
        """ Stop everything.
        """
        with self._lock:
            self._closed = True
            workers = list(self._workers.values())
            self._workers.clear()

        for _, stop in workers:
            stop.set()

    def _queue_for(self, user_id: int):
        with self._lock:
            if self._closed:
                return None

            worker = self._workers.get(user_id)
            if worker is not None:
                return worker[0]

            if not self._is_allowed(user_id):
                return None

            q = queue.Queue(self._queue_size)
            stop = threading.Event()
            self._workers[user_id] = (q, stop)

        thread = threading.Thread(target=self._run, args=(user_id, q, stop),
                                  name=f"speech-{user_id}", daemon=True)
        thread.start()
        return q

    def _run(self, user_id: int, q: queue.Queue, stop: threading.Event):
        try:
            detector = self._make_detector()
        except Exception:
            log.exception("could not create a recognizer for %s", user_id)
            return

        while not stop.is_set():
            try:
                try:
                    pcm = q.get(timeout=self._idle_seconds)
                except queue.Empty:
                    hit = detector.flush()  # they went quiet: let it finish the sentence
                else:
                    hit = detector.feed(pcm)
            except Exception:
                log.exception("speech recognition error for %s", user_id)
                continue

            if hit:
                self._fire(user_id)

    def _fire(self, user_id: int):
        with self._lock:
            now = time.monotonic()
            if now - self._last_fire < self._cooldown:
                return
            self._last_fire = now

        try:
            self._on_trigger(user_id)
        except Exception:
            log.exception("trigger handler failed")
