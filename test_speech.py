import threading
import time

from speech import SpeechWorkers


class FakeDetector:
    """ feed(b"HIT") -> True. flush() -> True if flush_hits. """

    def __init__(self, flush_hits=False, fail_first=False):
        self.flush_hits = flush_hits
        self.fail_first = fail_first
        self.fed = []
        self.flushes = 0

    def feed(self, pcm):
        if self.fail_first:
            self.fail_first = False
            raise RuntimeError("boom")
        self.fed.append(pcm)
        return pcm == b"HIT"

    def flush(self):
        self.flushes += 1
        return self.flush_hits


def make_workers(detector_factory=FakeDetector, **kwargs):
    triggers = []
    event = threading.Event()

    def on_trigger(user_id):
        triggers.append(user_id)
        event.set()

    kwargs.setdefault("idle_seconds", 0.02)
    kwargs.setdefault("cooldown", 0.0)
    return SpeechWorkers(detector_factory, on_trigger, **kwargs), triggers, event


def test_trigger_calls_back_with_the_speaker():
    workers, triggers, event = make_workers()
    workers.feed(7, b"hello")
    workers.feed(7, b"HIT")
    assert event.wait(1)
    assert triggers == [7]
    workers.close()


def test_one_detector_per_speaker():
    created = []

    def factory():
        created.append(1)
        return FakeDetector()

    workers, _, _ = make_workers(factory)
    workers.feed(1, b"a")
    workers.feed(1, b"b")
    workers.feed(2, b"c")
    time.sleep(0.2)
    assert len(created) == 2
    workers.close()


def test_cooldown_ignores_a_second_trigger():
    workers, triggers, event = make_workers(cooldown=0.3)
    workers.feed(1, b"HIT")
    workers.feed(2, b"HIT")
    time.sleep(0.2)
    assert len(triggers) == 1

    time.sleep(0.3)
    workers.feed(1, b"HIT")
    time.sleep(0.2)
    assert len(triggers) == 2
    workers.close()


def test_feed_never_blocks_even_when_the_detector_is_slow():
    class SlowDetector(FakeDetector):
        def feed(self, pcm):
            time.sleep(0.5)
            return False

    workers, _, _ = make_workers(SlowDetector, queue_size=10)
    start = time.monotonic()
    for _ in range(1000):
        workers.feed(1, b"x")
    assert time.monotonic() - start < 0.3
    workers.close()


def test_idle_speaker_gets_flushed():
    detectors = []

    def factory():
        d = FakeDetector(flush_hits=True)
        detectors.append(d)
        return d

    workers, triggers, event = make_workers(factory)
    workers.feed(1, b"some speech")
    assert event.wait(1)  # the flush after they went quiet found the phrase
    assert triggers == [1]
    assert detectors[0].flushes >= 1
    workers.close()


def test_removed_speaker_is_not_recreated_when_not_allowed():
    created = []
    allowed = {1}

    def factory():
        created.append(1)
        return FakeDetector()

    workers, _, _ = make_workers(factory, is_allowed=lambda uid: uid in allowed)
    workers.feed(1, b"a")
    time.sleep(0.1)
    assert len(created) == 1

    allowed.discard(1)
    workers.remove(1)
    workers.feed(1, b"late packet")  # a packet that was already in flight
    time.sleep(0.1)
    assert len(created) == 1
    workers.close()


def test_remove_stops_the_thread():
    workers, _, _ = make_workers()
    workers.feed(5, b"a")
    time.sleep(0.1)
    assert any(t.name == "speech-5" for t in threading.enumerate())

    workers.remove(5)
    time.sleep(0.2)
    assert not any(t.name == "speech-5" for t in threading.enumerate())
    workers.close()


def test_close_stops_every_thread_and_ignores_new_audio():
    workers, _, _ = make_workers()
    workers.feed(1, b"a")
    workers.feed(2, b"b")
    workers.close()
    workers.feed(3, b"c")
    time.sleep(0.2)
    assert not any(t.name.startswith("speech-") for t in threading.enumerate())


def test_an_error_in_the_detector_does_not_kill_the_worker():
    workers, triggers, event = make_workers(lambda: FakeDetector(fail_first=True))
    workers.feed(1, b"this one raises")
    workers.feed(1, b"HIT")
    assert event.wait(1)
    assert triggers == [1]
    workers.close()
