import os

from discord.ext import commands
from dotenv import load_dotenv
from loguru import logger

from utils.tools import error_output

load_dotenv()


class EventListener(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        try:
            channel = self.bot.get_channel(
                int(os.getenv('VOICE_STATUS_CHANNEL_ID')))
        except:
            logger.error('頻道取得失敗')
            return
        logger.info(str(member))
        logger.info(str(before.channel))
        logger.info(str(after.channel))
        await channel.send(f'{str(member)}語音狀態改變: {str(before.channel)} -> {str(after.channel)}')


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EventListener(bot), guild=None)
