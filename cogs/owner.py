import discord

from discord import app_commands
from discord.ext import commands
from loguru import logger

from utils.tools import error_output, owner_output


class Owner(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def check_owner(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != str(self.bot.owner_id):
            await interaction.response.send_message(embed=await owner_output('Only bot owner can use this command!'), ephemeral=True)
            return False
        return True

    @app_commands.command(name='close', description='close bot(owner only)')
    async def close(self, interaction: discord.Interaction):
        if not await self.check_owner(interaction):
            return
        try:
            logger.info('正在關閉機器人...')
            await interaction.response.send_message(embed=await owner_output('正在關閉機器人...'), ephemeral=True)
            await self.bot.close()
        except Exception as e:
            logger.error(e)
            await interaction.response.send_message(embed=await error_output(e))

    @app_commands.command(name='change_presence', description='change bot presence(owner only)')
    @app_commands.describe(status='The status for bot.')
    @app_commands.choices(status=[
        app_commands.Choice(name='playing', value='playing'),
        app_commands.Choice(name='streaming', value='streaming'),
        app_commands.Choice(name='listening', value='listening'),
        app_commands.Choice(name='watching', value='watching'),
        app_commands.Choice(name='custom', value='custom'),
        app_commands.Choice(name='competing', value='competing'),
    ])
    async def change_presence(self, interaction: discord.Interaction, status: str, name: str):
        if not await self.check_owner(interaction):
            await interaction.response.send_message('Only bot owner can use this command!', ephemeral=True)
            return
        try:
            match status:
                case 'playing':
                    act = discord.Activity(
                        type=discord.ActivityType.playing, name=name)
                case 'streaming':
                    act = discord.Activity(
                        type=discord.ActivityType.streaming, name=name)
                case 'listening':
                    act = discord.Activity(
                        type=discord.ActivityType.listening, name=name)
                case 'watching':
                    act = discord.Activity(
                        type=discord.ActivityType.watching, name=name)
                case 'custom':
                    act = discord.Activity(
                        type=discord.ActivityType.custom, name=name)
                case 'competing':
                    act = discord.Activity(
                        type=discord.ActivityType.competing, name=name)
            await self.bot.change_presence(activity=act, status=discord.Status.online)
            await interaction.response.send_message(embed=await owner_output('更改機器人狀況成功!'), ephemeral=True)
            # TODO add other optional
        except Exception as e:
            logger.error(e)
            await interaction.response.send_message(embed=await error_output(e))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Owner(bot), guild=None)
