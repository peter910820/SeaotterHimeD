import datetime
import discord

from dataclasses import dataclass


@dataclass
class ServerInfoStruct:
    guild_id: int
    created_at: datetime.datetime
    description: str | None
    member_count: int
    icon: discord.Asset
