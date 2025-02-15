import discord

from discord import app_commands
from discord.ext import commands
from loguru import logger

from utils.embed_output import error_output, general_output


class General(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name='ping', description='return bot delay')
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=await general_output(f'delay time: {str(round(self.bot.latency*1000, 3))}ms.'))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(General(bot), guild=None)
