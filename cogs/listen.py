import asyncio
import io
import logging
import time
import wave
from dataclasses import dataclass

import discord
from discord import app_commands
from discord.ext import commands, voice_recv

from buffers import UserBuffers
from export import build_clip, render_tracks
from sink import ClipSink
from speech import SpeechWorkers
from trigger import TriggerDetector

log = logging.getLogger(__name__)

CLIP_SECONDS = 30
CLIP_CHANNEL_NAME = "clip-that"


@dataclass
class Session:
    """ Everything that exists while the bot is listening in one server. """
    vc: voice_recv.VoiceRecvClient
    buffers: UserBuffers
    opted_in: set[int]       # shared with the sink, so opt-in/out takes effect live
    speech: SpeechWorkers


def snapshot(buffers: UserBuffers):
    """ Take ONE shared window_start, and copy the buffers so the audio thread
        can't change them while we render. Do this first, before any await. """
    window_start = time.monotonic() - buffers.seconds
    entries = {uid: list(dq) for uid, dq in list(buffers.buffer.items())}
    return entries, window_start


class Listen(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.sessions: dict[int, Session] = {}  # guild_id -> Session

    def cog_unload(self):
        for session in self.sessions.values():
            session.speech.close()

    # ------------------------------------------------------------------
    # sessions
    # ------------------------------------------------------------------

    async def start_session(self, guild: discord.Guild, channel: discord.VoiceChannel) -> Session:
        opted_in = self.bot.db.opted_in_users(guild.id)
        buffers = UserBuffers(CLIP_SECONDS)

        def on_trigger(user_id: int):
            # runs on a speech worker thread, so hand over to the bot's event loop
            asyncio.run_coroutine_threadsafe(self.handle_trigger(guild.id, user_id), self.bot.loop)

        speech = SpeechWorkers(
            make_detector=lambda: TriggerDetector(self.bot.vosk_model),
            on_trigger=on_trigger,
            is_allowed=lambda user_id: user_id in opted_in,
        )
        sink = ClipSink(buffers, opted_in, speech)

        if guild.voice_client is not None:  # left over from a crash or a restart
            await guild.voice_client.disconnect(force=True)

        vc = await channel.connect(cls=voice_recv.VoiceRecvClient)
        try:
            vc.listen(sink)
        except Exception:
            await vc.disconnect()
            raise

        session = Session(vc, buffers, opted_in, speech)
        self.sessions[guild.id] = session
        return session

    async def stop_session(self, guild_id: int) -> bool:
        session = self.sessions.pop(guild_id, None)
        if session is None:
            return False

        session.speech.close()
        session.vc.stop_listening()
        await session.vc.disconnect()
        return True

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # if the bot gets kicked or disconnected, forget the session
        if member.id == self.bot.user.id and after.channel is None:
            session = self.sessions.pop(member.guild.id, None)
            if session is not None:
                session.speech.close()

    def consent_changed(self, guild_id: int, user_id: int, opted_in: bool):
        """ Called by the consent commands so opting in/out takes effect right away. """
        session = self.sessions.get(guild_id)
        if session is None:
            return

        if opted_in:
            session.opted_in.add(user_id)
        else:
            session.opted_in.discard(user_id)
            session.speech.remove(user_id)
            session.buffers.clear(user_id)

    # ------------------------------------------------------------------
    # making and posting clips
    # ------------------------------------------------------------------

    async def render_clip(self, guild: discord.Guild, buffers: UserBuffers):
        """ Snapshot, render, mix, encode, zip.
            Returns (mixed_mp3, zip_bytes), or None if there's nothing to clip.
        """
        entries, window_start = snapshot(buffers)  # no await before this

        names = {}
        for uid in entries:
            member = guild.get_member(uid)
            if member:
                names[uid] = member.name

        def work():
            tracks = render_tracks(entries, window_start, buffers.seconds)
            return build_clip(tracks, names)

        return await asyncio.to_thread(work)  # off the event loop

    def clip_files(self, result, size_limit: int):
        """ Turns (mixed_mp3, zip_bytes) into discord.File objects.
            Returns (files, note), where note says if something was left out. """
        mixed_mp3, zip_bytes = result
        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")

        files = [discord.File(io.BytesIO(mixed_mp3), f"clip-{timestamp}.mp3")]
        note = ""

        if len(zip_bytes) <= size_limit:
            files.append(discord.File(io.BytesIO(zip_bytes), f"{timestamp}-tracks.zip"))
        else:
            note = " (the per-person zip was too big to upload)"

        return files, note

    async def get_clip_channel(self, guild: discord.Guild):
        """ Finds #clip-that, creating it if it doesn't exist.
            Returns None if we can't (no permission). """
        channel = discord.utils.get(guild.text_channels, name=CLIP_CHANNEL_NAME)

        if channel is None:
            try:
                channel = await guild.create_text_channel(CLIP_CHANNEL_NAME, reason="Clip That posts clips here")
            except (discord.Forbidden, discord.HTTPException):
                return None

        perms = channel.permissions_for(guild.me)
        if not (perms.view_channel and perms.send_messages and perms.attach_files):
            return None

        return channel

    async def complain(self, guild: discord.Guild, text: str):
        """ Say something in any channel the bot is allowed to type in. """
        candidates = [guild.system_channel] + list(guild.text_channels)
        for channel in candidates:
            if channel is not None and channel.permissions_for(guild.me).send_messages:
                try:
                    await channel.send(text)
                except discord.HTTPException:
                    continue
                return

    async def clip_to_channel(self, guild: discord.Guild, buffers: UserBuffers, requester_id: int) -> str:
        """ Renders a clip and posts it to #clip-that. Returns a short status message. """
        result = await self.render_clip(guild, buffers)
        if result is None:
            return "Nothing to clip."

        channel = await self.get_clip_channel(guild)
        if channel is None:
            await self.complain(
                guild,
                f"I couldn't use #{CLIP_CHANNEL_NAME}. Please create a text channel with that name "
                "that I can send messages and attach files in (or give me the Manage Channels permission).",
            )
            return f"I couldn't post the clip because I can't use #{CLIP_CHANNEL_NAME}."

        files, note = self.clip_files(result, guild.filesize_limit)

        try:
            await channel.send(
                f"Clip saved by <@{requester_id}>{note}",
                files=files,
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except discord.HTTPException:
            log.exception("posting the clip failed")
            await self.complain(guild, f"I couldn't post to #{CLIP_CHANNEL_NAME} (is the file too large?).")
            return "I couldn't post the clip."

        return f"Clip saved in {channel.mention}."

    async def handle_trigger(self, guild_id: int, user_id: int):
        """ Someone said "clip that". """
        session = self.sessions.get(guild_id)
        guild = self.bot.get_guild(guild_id)
        if session is None or guild is None:
            return

        try:
            await self.clip_to_channel(guild, session.buffers, user_id)
        except Exception:
            log.exception("clip trigger failed")

    # ------------------------------------------------------------------
    # commands
    # ------------------------------------------------------------------

    @app_commands.command(name="listen", description="Join your voice channel and listen for \"clip that\"")
    @app_commands.guild_only()
    async def listen(self, interaction: discord.Interaction):
        if interaction.guild_id in self.sessions:
            return await interaction.response.send_message("Already listening.", ephemeral=True)

        voice = interaction.user.voice
        if not voice:
            return await interaction.response.send_message("Join a voice channel first!", ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        try:
            await self.start_session(interaction.guild, voice.channel)
        except (discord.ClientException, discord.Forbidden, asyncio.TimeoutError):
            log.exception("could not start listening")
            return await interaction.followup.send("I couldn't join that voice channel.", ephemeral=True)

        await interaction.followup.send(
            "Listening. Opted-in people can say \"clip that\" (or use `/clip`).", ephemeral=True
        )

    @app_commands.command(name="unlisten", description="Stop listening and leave the call")
    @app_commands.guild_only()
    async def unlisten(self, interaction: discord.Interaction):
        if not await self.stop_session(interaction.guild_id):
            return await interaction.response.send_message("I'm not listening here.", ephemeral=True)

        await interaction.response.send_message("Stopped listening.", ephemeral=True)

    @app_commands.command(name="clip", description="Save the last chunk of the call to #clip-that")
    @app_commands.guild_only()
    async def clip(self, interaction: discord.Interaction):
        session = self.sessions.get(interaction.guild_id)

        if session is None:
            await interaction.response.send_message("I'm not currently listening.", ephemeral=True)
            return

        if not self.bot.db.is_opted_in(interaction.guild_id, interaction.user.id):
            await interaction.response.send_message("Only opted-in people can clip.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)  # rendering takes a moment

        status = await self.clip_to_channel(interaction.guild, session.buffers, interaction.user.id)
        await interaction.followup.send(status, ephemeral=True)

    @app_commands.command(name="dump", description="DEBUG: each person's buffered audio as wav files")
    @app_commands.guild_only()
    async def dump(self, interaction: discord.Interaction):
        session = self.sessions.get(interaction.guild_id)

        if session is None:
            return await interaction.response.send_message("I'm not currently listening.", ephemeral=True)

        if not self.bot.db.is_opted_in(interaction.guild_id, interaction.user.id):
            return await interaction.response.send_message("Only opted-in people can do that.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        entries, window_start = snapshot(session.buffers)
        tracks = await asyncio.to_thread(render_tracks, entries, window_start, session.buffers.seconds)

        if not tracks:
            return await interaction.followup.send("Nothing recorded.", ephemeral=True)

        files = [discord.File(self.pcm_to_wav(pcm), f"{uid}.wav") for uid, pcm in tracks.items()]
        await interaction.followup.send("Recorded:", files=files, ephemeral=True)

    def pcm_to_wav(self, pcm: bytes) -> io.BytesIO:
        out = io.BytesIO()
        with wave.open(out, "wb") as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(48000)
            w.writeframes(pcm)
        out.seek(0)
        return out


async def setup(bot):
    await bot.add_cog(Listen(bot))