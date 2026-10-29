import asyncio
import threading

from buffers import UserBuffers
from cogs.listen import Listen, Session, snapshot
from cogs.consent import Consent
from speech import SpeechWorkers


class FakeBot:
    def __init__(self):
        self.cogs = {}

    def get_cog(self, name):
        return self.cogs.get(name)


class FakeDetector:
    def feed(self, pcm):
        return False

    def flush(self):
        return False


def make_session():
    opted_in = {1, 2}
    buffers = UserBuffers(30)
    speech = SpeechWorkers(FakeDetector, lambda uid: None, is_allowed=lambda uid: uid in opted_in, idle_seconds=0.02)
    return Session(vc=None, buffers=buffers, opted_in=opted_in, speech=speech)


def test_opt_out_takes_effect_live():
    bot = FakeBot()
    cog = Listen(bot)
    session = make_session()
    cog.sessions[10] = session

    session.buffers.add(1, b"x" * 3840, 5000, 1)
    session.speech.feed(1, b"x")

    cog.consent_changed(10, 1, False)

    assert 1 not in session.opted_in          # the sink will now ignore them
    assert 1 not in session.buffers.buffer    # their buffered audio is wiped
    assert 2 in session.opted_in              # other people are untouched
    session.speech.close()


def test_opt_in_takes_effect_live():
    bot = FakeBot()
    cog = Listen(bot)
    session = make_session()
    cog.sessions[10] = session

    cog.consent_changed(10, 99, True)
    assert 99 in session.opted_in
    session.speech.close()


def test_consent_change_with_no_session_is_a_no_op():
    Listen(FakeBot()).consent_changed(10, 1, False)  # must not raise


def test_consent_cog_forwards_to_listen_cog():
    bot = FakeBot()
    listen = Listen(bot)
    session = make_session()
    listen.sessions[10] = session
    bot.cogs["Listen"] = listen

    Consent(bot).sync_live(10, 1, False)
    assert 1 not in session.opted_in


def test_consent_cog_works_when_listen_cog_is_missing():
    Consent(FakeBot()).sync_live(10, 1, False)  # must not raise


def test_snapshot_copies_deques():
    buffers = UserBuffers(30)
    buffers.add(1, b"a" * 3840, 5000, 1)
    entries, window_start = snapshot(buffers)
    buffers.add(1, b"b" * 3840, 5960, 1)
    assert len(entries[1]) == 1  # the later packet isn't in the snapshot


def test_clip_files_leaves_out_an_oversized_zip():
    cog = Listen(FakeBot())
    files, note = cog.clip_files((b"mp3", b"z" * 100), size_limit=50)
    assert len(files) == 1 and "too big" in note
    files, note = cog.clip_files((b"mp3", b"z" * 10), size_limit=50)
    assert len(files) == 2 and note == ""
