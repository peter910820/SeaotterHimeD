import discord

from discord import app_commands
from discord.ext import commands

from utils.embed_output import info_output
from common.structure import ServerInfoStruct


class Info(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name='get_userid', description='get user id for yourself')
    async def get_id(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=await info_output(f'Your user ID: {interaction.user.id}'))

    @app_commands.command(name='get_guildid', description='get current guild id')
    async def get_guildid(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=await info_output(f'Current guild ID: {interaction.guild_id}'))

    @app_commands.command(name='get_serverinfo', description='get current server info')
    async def get_serverinfo(self, interaction: discord.Interaction):
        server_info = ServerInfoStruct(
            guild_id=interaction.guild_id,
            created_at=interaction.guild.created_at,
            description=interaction.guild.description,
            member_count=interaction.guild.member_count,
            icon=interaction.guild.icon,
        )
        await interaction.response.send_message(embed=await info_output(server_info))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Info(bot), guild=None)
