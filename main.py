import discord
import os

from discord.ext import commands
from dotenv import load_dotenv
from loguru import logger

load_dotenv()


class SeaotterHimeD(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(
            command_prefix=">",
            intents=intents,
            owner_id=os.getenv('BOT_OWNER')
        )

    async def setup_hook(self):

        # This is a event_listener listen on_voice_state_update
        # await self.load_extension('listener.event_listener')
        await self.load_extension('cogs.general')
        await self.load_extension('cogs.owner')
        await self.load_extension('cogs.youtube_palyer')
        await bot.tree.sync(guild=None)

    async def on_ready(self):
        logger.info(f'{self.user} is online')
        status = discord.Activity(
            type=discord.ActivityType.playing, name='Galgame')
        await self.change_presence(status=discord.Status.online, activity=status)


bot = SeaotterHimeD()
bot.run(os.getenv('BOT_TOKEN'))
