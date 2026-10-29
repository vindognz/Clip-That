import discord
from discord import app_commands
from discord.ext import commands


class Consent(commands.Cog):
    """/opt-in and /opt-out. Consent is per user per server, and the default is opted out."""

    def __init__(self, bot):
        self.bot = bot

    def sync_live(self, guild_id: int, user_id: int, opted_in: bool):
        # if the bot is listening right now, make the change take effect immediately
        listen = self.bot.get_cog("Listen")
        if listen is not None:
            listen.consent_changed(guild_id, user_id, opted_in)

    @app_commands.command(name="opt-in", description="Let Clip That use your voice in clips")
    @app_commands.guild_only()
    async def opt_in(self, interaction: discord.Interaction):
        newly = self.bot.db.opt_in(interaction.guild_id, interaction.user.id)
        self.sync_live(interaction.guild_id, interaction.user.id, True)

        if newly:
            msg = (
                "You're opted in! When you're in a call with me, your voice is buffered in memory, "
                "and if someone says \"clip that\", **your voice may be posted in #clip-that**.\n"
                "Use `/opt-out` any time to stop."
            )
        else:
            msg = "You're already opted in. Use `/opt-out` to stop."

        await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.command(name="opt-out", description="Stop Clip That from using your voice")
    @app_commands.guild_only()
    async def opt_out(self, interaction: discord.Interaction):
        was_opted_in = self.bot.db.opt_out(interaction.guild_id, interaction.user.id)
        self.sync_live(interaction.guild_id, interaction.user.id, False)

        if was_opted_in:
            msg = (
                "You're opted out. I've stopped using your voice and wiped what I had buffered. "
                "Clips that were already posted stay posted."
            )
        else:
            msg = "You're already opted out (that's the default)."

        await interaction.response.send_message(msg, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Consent(bot))