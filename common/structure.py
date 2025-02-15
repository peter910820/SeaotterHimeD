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


class CustomError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)

    def __str__(self):
        return f"CustomError: {self.message}"
