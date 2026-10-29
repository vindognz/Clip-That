import json

from trigger import TriggerDetector, SILENCE_SECONDS

HIT = {'result': [{'conf': 1.0, 'end': 23.34, 'start': 22.95, 'word': 'clip'}, {'conf': 1.0, 'end': 23.64, 'start': 23.34, 'word': 'that'}], 'text': 'clip that'}
MISS = {'result': [{'conf': 1.0, 'end': 5.3, 'start': 4.9, 'word': 'click'}, {'conf': 1.0, 'end': 5.6, 'start': 5.3, 'word': 'that'}], 'text': 'click that'}

PACKET = bytes(3840)  # 20ms of 48kHz stereo


class FakeRecognizer:
    """ Pretends to be a Vosk KaldiRecognizer.
        endpoints: the results to return, in order, on the calls where it "finishes a sentence".
        end_on_call: which call numbers (1-based) finish a sentence. """

    def __init__(self, end_on_call=(), results=()):
        self.calls = []
        self.end_on_call = set(end_on_call)
        self.results = list(results)

    def AcceptWaveform(self, data):
        self.calls.append(data)
        return len(self.calls) in self.end_on_call

    def Result(self):
        return json.dumps(self.results.pop(0))


def test_feed_converts_packets_to_16k_mono():
    rec = FakeRecognizer()
    TriggerDetector(recognizer=rec).feed(PACKET)
    assert len(rec.calls[0]) == 640  # 20ms of 16kHz 16-bit mono


def test_feed_returns_false_mid_sentence():
    detector = TriggerDetector(recognizer=FakeRecognizer())
    assert detector.feed(PACKET) is False


def test_feed_returns_true_when_a_finished_sentence_has_the_phrase():
    detector = TriggerDetector(recognizer=FakeRecognizer(end_on_call=[1], results=[HIT]))
    assert detector.feed(PACKET) is True


def test_feed_returns_false_when_a_finished_sentence_does_not_have_it():
    detector = TriggerDetector(recognizer=FakeRecognizer(end_on_call=[1], results=[MISS]))
    assert detector.feed(PACKET) is False


def test_flush_does_nothing_if_nothing_was_said():
    rec = FakeRecognizer()
    detector = TriggerDetector(recognizer=rec)
    assert detector.flush() is False
    assert rec.calls == []


def test_flush_feeds_silence_after_speech():
    rec = FakeRecognizer()
    detector = TriggerDetector(recognizer=rec)
    detector.feed(PACKET)
    detector.flush()

    silence_calls = rec.calls[1:]
    assert len(silence_calls) == int(SILENCE_SECONDS / 0.02)
    assert all(call == bytes(640) for call in silence_calls)


def test_flush_reports_a_phrase_finished_by_the_silence():
    # call 1 is the speech, call 10 is partway through the silence
    rec = FakeRecognizer(end_on_call=[10], results=[HIT])
    detector = TriggerDetector(recognizer=rec)
    detector.feed(PACKET)
    assert detector.flush() is True
    assert len(rec.calls) == 10  # stopped feeding once it had its answer


def test_flush_only_happens_once_per_sentence():
    rec = FakeRecognizer()
    detector = TriggerDetector(recognizer=rec)
    detector.feed(PACKET)
    detector.flush()
    calls_after_first = len(rec.calls)
    detector.flush()
    assert len(rec.calls) == calls_after_first


def test_new_speech_after_a_flush_can_be_flushed_again():
    rec = FakeRecognizer()
    detector = TriggerDetector(recognizer=rec)
    detector.feed(PACKET)
    detector.flush()
    detector.feed(PACKET)
    before = len(rec.calls)
    detector.flush()
    assert len(rec.calls) > before
