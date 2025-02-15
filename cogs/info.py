import discord

from discord import app_commands
from discord.ext import commands
from typing import cast

from utils.embed_output import info_output
from common.structure import ServerInfoStruct


class Info(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name='get_userid', description='get user id for yourself')
    async def get_userid(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=await info_output(f'Your user ID: {interaction.user.id}'))

    @app_commands.command(name='get_guildid', description='get current guild id')
    async def get_guildid(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=await info_output(f'Current guild ID: {interaction.guild_id}'))

    @app_commands.command(name='get_serverinfo', description='get current server info')
    async def get_serverinfo(self, interaction: discord.Interaction):
        guild_info = cast(discord.Guild, interaction.guild)
        server_info = ServerInfoStruct(
            guild_id=cast(int, interaction.guild_id),
            created_at=guild_info.created_at,
            description=guild_info.description,
            member_count=cast(int, guild_info.member_count),
            icon=cast(discord.Asset, guild_info.icon),
        )
        await interaction.response.send_message(embed=await info_output(server_info))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Info(bot), guild=None)
