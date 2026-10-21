import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv() # loads DISCORD_TOKEN into an env variable

class ClipBot(commands.Bot):
    def __init__(self):
        # intents = the events discord sends the bot
        intents = discord.Intents.default()

        # setup for slash commands
        super().__init__(command_prefix = commands.when_mentioned, intents = intents)

    async def setup_hook(self):
        # runs once before the bot connects
        # registers the slash commands
        await self.tree.sync()

    async def on_ready(self):
        print(f"Logged in as {self.user} (id: {self.user.id})")

bot = ClipBot()

@bot.tree.command(name="ping", description="Check the bot is alive")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"Pong! {round(bot.latency * 1000)}ms")


if __name__ == "__main__":
    bot.run(os.environ["DISCORD_TOKEN"])