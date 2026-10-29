import os

import discord
from discord.ext import commands
from dotenv import load_dotenv
from vosk import Model

from db import Database
from trigger import MODEL_PATH

load_dotenv()


class ClipBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix=commands.when_mentioned, intents=intents)

        self.db = Database("clip_that.db")
        self.vosk_model = Model(MODEL_PATH)  # loaded once, shared by every speaker

    async def setup_hook(self):
        await self.load_extension("cogs.consent")
        await self.load_extension("cogs.listen")
        await self.tree.sync()

    async def on_ready(self):
        print(f"Logged in as {self.user} (id: {self.user.id})")


bot = ClipBot()


@bot.tree.command(name="ping", description="Check the bot is alive")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"Pong! {round(bot.latency * 1000)}ms")


if __name__ == "__main__":
    bot.run(os.environ["DISCORD_TOKEN"])