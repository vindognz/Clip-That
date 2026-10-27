import discord
from discord import app_commands
from discord.ext import commands, voice_recv

from buffers import UserBuffers
from sink import ClipSink
from audio import render_track_rtp
from export import render_tracks, build_clip

import io
import wave
import time
import asyncio

class Listen(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.sessions = {}

    def pcm_to_wav(self, pcm: bytes) -> io.BytesIO:
        out = io.BytesIO()
        with wave.open(out, "wb") as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(48000)
            w.writeframes(pcm)
        out.seek(0)
        return out

    @app_commands.command(name="listen", description="temp bruh")
    @app_commands.guild_only()
    async def listen(self, interaction: discord.Interaction):
        session = self.sessions.get(interaction.guild_id, None)

        if session:
            return await interaction.response.send_message("Already recording", ephemeral=True)

        voice = interaction.user.voice

        if not voice:
            return await interaction.response.send_message("you aint in a vc twin", ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        opted_in = self.bot.db.opted_in_users(interaction.guild_id)
        vc = await voice.channel.connect(cls=voice_recv.VoiceRecvClient)
        buffers = UserBuffers(30)
        sink = ClipSink(buffers, opted_in)

        vc.listen(sink)

        self.sessions[interaction.guild_id] = (vc, buffers)

        return await interaction.followup.send("Starting recording", ephemeral=True)

    @app_commands.command(name="dump", description="TEMP")
    @app_commands.guild_only()
    async def dump(self, interaction: discord.Interaction):
        session = self.sessions.get(interaction.guild_id, None)

        await interaction.response.defer(ephemeral=True)

        if session is None:
            return await interaction.followup.send("No current session", ephemeral=True)

        buffers: UserBuffers = session[1]

        if not buffers.buffer:
            return await interaction.followup.send("Nothing recorded.")

        window_start = time.monotonic() - buffers.seconds

        files = []
        report = []
        for user_id, dq in list(buffers.buffer.items()):
            packets = len(dq)
            seconds = packets * 0.02
            report.append(f"<@{user_id}>: talked for {seconds:.1f}s")
            chunks = list(dq)
            # pcm = b"".join(chunk for _, chunk in chunks)
            pcm = render_track_rtp(chunks, window_start, buffers.seconds)
            files.append(discord.File(self.pcm_to_wav(pcm), f"{user_id}.wav"))


        await interaction.followup.send("Recorded:\n" + '\n'.join(report), files=files)

    @app_commands.command(name="unlisten", description="Temp (stop and leave)")
    @app_commands.guild_only()
    async def unlisten(self, interaction: discord.Interaction):
        session = self.sessions.pop(interaction.guild_id, None)

        if session is None:
            return await interaction.response.send_message("No current session", ephemeral=True)

        vc: voice_recv.VoiceRecvClient = session[0]
        vc.stop_listening()
        await vc.disconnect()

        return await interaction.response.send_message("Stopped listening...", ephemeral=True)


    @app_commands.command(name="clip", description="Save the last chunk of the call")
    @app_commands.guild_only()
    async def clip(self, interaction: discord.Interaction):
        session = self.sessions.get(interaction.guild_id)

        if session is None:
            await interaction.response.send_message("I'm not currently listening.", ephemeral=True)
            return

        if not self.bot.db.is_opted_in(interaction.guild_id, interaction.user.id):
            await interaction.response.send_message("Only opted-in people can clip.", ephemeral=True)
            return

        buffers: UserBuffers = session[1]
        window_start = time.monotonic() - buffers.seconds
        
        entries = {uid: list(dq) for uid, dq in list(buffers.buffer.items())} # snapshot so audio thread can't screw with it

        await interaction.response.defer()

        names = {}
        for uid in entries:
            member = interaction.guild.get_member(uid)
            if member:
                names[uid] = member.name

        def work():
            tracks = render_tracks(entries, window_start, buffers.seconds)
            return build_clip(tracks, names)

        result = await asyncio.to_thread(work) # off the event loop

        if result is None:
            await interaction.followup.send("Nothing to clip.")
            return

        mixed_mp3 = result[0]
        zip_bytes = result[1]

        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")

        mixed_file = discord.File(io.BytesIO(mixed_mp3), f"clip-{timestamp}.mp3")
        zip_file = discord.File(io.BytesIO(zip_bytes), f"{timestamp}-tracks.zip")

        await interaction.followup.send(files=[mixed_file, zip_file])

async def setup(bot):
    await bot.add_cog(Listen(bot))
