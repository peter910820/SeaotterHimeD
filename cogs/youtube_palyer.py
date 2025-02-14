import asyncio
import discord
import os
import re
import yt_dlp

from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from loguru import logger

from utils.tools import error_output, youtube_palyer_output, youtube_palyer_notice_output

load_dotenv()


class YotubePlayer(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.forbidden_char = re.compile(r'[/\\:*?"\'<>|\.]')
        self.play_queue = []
        self.channel_id = []
        self.text_channel_id = None
        self.pause_flag = False
        self.ffmpeg_path = os.getenv('FFMPEG_PATH')
        self.song_path = './music_tmp/'
        self.cookie_path = './cookies.txt'
        self.volume = 0.1
        self.notice = False
        self.get_details_options = {
            'cookiefile': self.cookie_path,
            'extract_flat': True,  # dont download
            'quiet': True,  # undisplay progress bar
            'noplaylist': False,  # playlist
        }
        self.ydl_opts_postprocessors = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '320',
        }]

    async def check_owner(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != str(self.bot.owner_id):
            await interaction.response.send_message(embed=await youtube_palyer_output('Only bot owner can use this command!'), ephemeral=True)
            return False
        return True

    @app_commands.command(name='youtube_palyer_search', description='Return specified internal class variable for youtube_palyer cog(owner only)')
    @app_commands.describe(c_var='Class variable name.')
    @app_commands.choices(c_var=[
        app_commands.Choice(name='channel_id', value='channel_id'),
        app_commands.Choice(name='text_channel_id', value='text_channel_id'),
        app_commands.Choice(name='volume', value='volume'),
        app_commands.Choice(name='get_details_options',
                            value='get_details_options'),
        app_commands.Choice(name='ydl_opts_postprocessors',
                            value='ydl_opts_postprocessors'),
    ])
    async def youtube_palyer_search(self, interaction: discord.Interaction, c_var: str) -> None:
        if not await self.check_owner(interaction):
            return
        match c_var:
            case 'channel_id':
                c_var_value = self.channel_id
            case 'text_channel_id':
                c_var_value = self.text_channel_id
            case 'volume':
                c_var_value = self.volume
            case 'get_details_options':
                c_var_value = self.get_details_options
            case 'ydl_opts_postprocessors':
                c_var_value = self.ydl_opts_postprocessors
        await interaction.response.send_message(embed=await youtube_palyer_output(str(c_var_value)), ephemeral=True)

    @app_commands.command(name='join', description='加入語音頻道')
    async def join(self, interaction: discord.Interaction, channel_id: str = '0') -> None:
        if await self.handle_connect(interaction, 'join', channel_id):
            await interaction.response.send_message(embed=await youtube_palyer_output('已加入頻道'))
        else:
            await interaction.response.send_message(embed=await youtube_palyer_output('加入頻道失敗，請確保使用者在語音頻道內且機器人不在其他語音頻道'))

    @app_commands.command(name='leave', description='離開語音頻道')
    async def leave(self, interaction: discord.Interaction) -> None:
        if await self.handle_connect(interaction, 'leave'):
            await interaction.response.send_message(embed=await youtube_palyer_output('離開語音頻道成功'))
        else:
            await interaction.response.send_message(embed=await youtube_palyer_output('機器人未加入頻道'))

    @app_commands.command(name='play', description='播放YT音樂')
    @app_commands.describe(notice='song notice, if not entered, Bot doesn\'t notify when song changes',
                           channel_id='Voice channel id, if not entered, the current channel will be used')
    @app_commands.choices(notice=[
        app_commands.Choice(name=False, value=0),
        app_commands.Choice(name=True, value=1),
    ])
    async def play(self, interaction: discord.Interaction, notice: int, youtube_url: str, channel_id: str = '0') -> None:
        self.notice = bool(notice)
        self.text_channel_id = interaction.channel
        await interaction.response.defer()
        youtube_url = self.url_format(youtube_url)
        if youtube_url == None:
            await interaction.followup.send(embed=await youtube_palyer_output('找不到歌曲喔'))
            return
        if await self.handle_connect(interaction, 'play', channel_id):
            try:
                await self.get_details(youtube_url)
            except Exception as e:
                logger.error(e)
                await interaction.followup.send(embed=await error_output(e))
                return
            if not self.bot.voice_clients[0].is_playing():
                await interaction.followup.send(embed=await youtube_palyer_output(f'歌曲/單已加入: 加入網址為{youtube_url} 即將開始播放歌曲~'))
                title = self.forbidden_char.sub(
                    '_', self.play_queue[0]['title'])
                url = self.play_queue[0]['url']
                music_path = f'{self.song_path}{title}'
                ydl_opts = {
                    'cookiefile': self.cookie_path,
                    'format': 'bestaudio/best',
                    'outtmpl': music_path,
                    'postprocessors': self.ydl_opts_postprocessors,
                }
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])
                except Exception as e:
                    logger.error(e)
                source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(
                    executable=self.ffmpeg_path, source=f'{music_path}.mp3'), volume=self.volume)
                self.bot.voice_clients[0].play(
                    source, after=lambda error: self.after_song_interface(
                        interaction, error)
                )
                if self.notice:
                    await interaction.followup.send(embed=await youtube_palyer_notice_output(self.play_queue[0]))
                await self.change_status(discord.Activity(
                    type=discord.ActivityType.listening, name=self.play_queue[0]['title']))
            else:
                await interaction.followup.send(embed=await youtube_palyer_output(f'歌曲已加入排序: 加入網址為{youtube_url}'))
        else:
            await interaction.followup.send(embed=await youtube_palyer_output('加入頻道失敗/未加入頻道'))

    def after_song_interface(self, interaction: discord.Interaction, error: Exception):
        if error:
            logger.error(str(error))
        else:
            logger.debug(str(error))
            self.bot.loop.create_task(self.after_song(interaction))

    async def after_song(self, interaction: discord.Interaction):
        self.play_queue.pop(0)
        if self.clean(self) == 1:
            await self.text_channel_id.send(embed=await youtube_palyer_output('正在嘗試重連...'))
            await asyncio.sleep(3)
        if len(self.bot.voice_clients) == 0:
            logger.warning('Reconnection failed, bot is ready to exit...')
            self.play_queue = []
            self.clean(self)
            await self.text_channel_id.send(embed=await youtube_palyer_output('機器人連線失敗，請稍後再使用'))
            self.channel_id = []
            return
        if len(self.play_queue) > 0:
            title = self.forbidden_char.sub('_', self.play_queue[0]['title'])
            url = self.play_queue[0]['url']
            music_path = f'{self.song_path}{title}'
            ydl_opts = {
                'cookiefile': self.cookie_path,
                'format': 'bestaudio/best',
                'outtmpl': music_path,
                'postprocessors': self.ydl_opts_postprocessors,
            }
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
            except Exception as e:
                logger.error(e)
            source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(
                executable=self.ffmpeg_path, source=f'{music_path}.mp3'), volume=self.volume)
            self.bot.voice_clients[0].play(
                source, after=lambda error: self.after_song_interface(
                    interaction, error)
            )
            if self.notice:
                await self.text_channel_id.send(embed=await youtube_palyer_notice_output(self.play_queue[0]))
            await self.change_status(discord.Activity(
                type=discord.ActivityType.listening, name=self.play_queue[0]['title']))
        else:
            await self.change_status(discord.Activity(
                type=discord.ActivityType.watching, name='ご注文はうさぎですか？'))
            logger.success('已播放完歌曲')
            await self.text_channel_id.send(embed=await youtube_palyer_output('已播放完歌曲'))
            self.channel_id = []

    @app_commands.command(name='skip', description='跳過歌曲')
    async def skip(self, interaction: discord.Interaction, count: int = 1) -> None:
        await interaction.response.defer()
        if count > 1:
            if count > len(self.play_queue):
                count = len(self.play_queue)
            count -= 1
            for _ in range(0, count):
                self.play_queue.pop(0)
        if len(self.play_queue) != 0:
            self.bot.voice_clients[0].stop()
        else:
            await interaction.followup.send(embed=await youtube_palyer_output('我還沒加入語音頻道呦'))
            return
        await interaction.followup.send(embed=await youtube_palyer_output('歌曲已跳過'))

    @app_commands.command(name='pause', description='暫停歌曲')
    async def pause(self, interaction) -> None:
        if self.bot.voice_clients[0].is_playing():
            self.bot.voice_clients[0].pause()
            self.pause_flag = True
            await interaction.response.send_message(embed=await youtube_palyer_output('歌曲已暫停'))
        else:
            await interaction.response.send_message(embed=await youtube_palyer_output('沒有歌曲正在播放'))

    @app_commands.command(name='resume', description='回復播放歌曲')
    async def resume(self, interaction) -> None:
        if self.bot.voice_clients[0].is_paused():
            self.bot.voice_clients[0].resume()
            self.pause_flag = False
            await interaction.response.send_message(embed=await youtube_palyer_output('歌曲已繼續播放'))
        else:
            await interaction.response.send_message(embed=await youtube_palyer_output('沒有歌曲正在暫停'))

    @app_commands.command(name='insert', description='插入歌曲到下一首')
    async def insert(self, interaction: discord.Interaction, youtube_url: str) -> None:
        await interaction.response.defer()
        youtube_url = self.url_format(youtube_url)
        if youtube_url.startswith('https://www.youtube.com/playlist?list='):
            await interaction.followup.send(embed=await youtube_palyer_output('此功能不支援清單插入呦'))
            return
        elif not youtube_url.startswith('https://www.youtube.com/'):
            await interaction.followup.send(embed=await youtube_palyer_output('找不到歌曲呦'))
        else:
            if await self.handle_connect(interaction, 'insert'):
                await interaction.followup.send(embed=await youtube_palyer_output('插入歌曲到下一首'))
                try:
                    with yt_dlp.YoutubeDL(self.get_details_options) as ydl:
                        details = ydl.extract_info(youtube_url, download=False)
                        if details.get('entries') == None:  # check if not a playlist
                            self.play_queue.insert(
                                1, {'url': youtube_url, 'title': details.get('title')})
                            logger.info(self.play_queue[1])
                        else:
                            logger.warning('不支援歌單插入')
                            await interaction.followup.send(embed=await youtube_palyer_output('不支援歌單插入'))
                except Exception as e:
                    logger.error(e)
            else:
                await interaction.followup.send(embed=await youtube_palyer_output('機器人未加入頻道'))

    @app_commands.command(name='list', description='查詢歌曲清單')
    async def list(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        if len(self.play_queue) == 0:
            await interaction.followup.send(embed=await youtube_palyer_output('播放清單目前為空'))
        else:
            display = f'播放清單剩餘歌曲: {len(self.play_queue)}首\n :arrow_forward: '
            for index, t in enumerate(self.play_queue, start=1):
                display += f'{index}. _{t["title"]}_\n'
                if len(display) >= 500:
                    display += '\n...還有很多首'
                    break
            logger.info(display)
            await interaction.followup.send(embed=await youtube_palyer_output(display))

    async def get_details(self, youtube_url: str) -> None:
        with yt_dlp.YoutubeDL(self.get_details_options) as ydl:
            details = ydl.extract_info(youtube_url, download=False)
            if details.get('entries') == None:  # check if not a playlist
                if details.get('title') not in {'[Deleted video]', '[Private video]'}:
                    song_details = [
                        {'url': youtube_url, 'title': details.get('title')}]
                else:
                    raise ValueError('該網址沒有影片/音樂')
            else:
                song_details = [entry for entry in details.get(
                    'entries') if entry.get('title') not in {'[Deleted video]', '[Private video]'}]
            logger.info(str(list(
                map(lambda x: {'url': x.get('url'), 'title': x.get('title')}, song_details))))
            self.play_queue.extend(song_details)

    def url_format(self, youtube_url: str) -> str | None:
        if '&list=' in youtube_url:
            youtube_url = youtube_url[0:youtube_url.find('&list=')]
        if youtube_url.startswith(('https://www.youtube.com/', 'https://youtube.com/', 'https://youtu.be/')):
            return youtube_url
        elif youtube_url.startswith('https://music.youtube.com/'):
            return youtube_url.replace('music', 'www')
        else:
            return None

    async def handle_connect(self, interaction: discord.Interaction, command: str, channel_id: str = '') -> bool:
        match command:
            case 'join' | 'play':
                try:
                    channel_id = int(channel_id)
                except ValueError:
                    logger.error('請輸入正確的channel_id!')
                    return False
                if len(self.bot.voice_clients) == 0:
                    if interaction.user.voice != None or channel_id != 0:
                        if channel_id == 0:
                            voice_channel = interaction.user.voice.channel
                        else:
                            voice_channel = self.bot.get_channel(channel_id)
                        try:
                            await voice_channel.connect()
                        except Exception as e:
                            logger.error(e)
                            logger.warning('channel does not exists!')
                            return False
                        self.channel_id.append(channel_id)
                        await self.change_status(discord.Activity(
                            type=discord.ActivityType.listening, name='Youtube'))
                        return True
                    return False
                else:
                    return False if command == 'join' else True
            case 'leave':
                if len(self.bot.voice_clients) != 0:
                    # The song hasn’t finished playing yet
                    if len(self.play_queue) != 0:
                        try:
                            self.play_queue = [self.play_queue[0]]
                            self.bot.voice_clients[0].stop()
                        except:
                            return True
                        await asyncio.sleep(1)  # Ensures the stop is complete
                    await self.bot.voice_clients[0].disconnect()
                    await self.change_status(discord.Activity(
                        type=discord.ActivityType.watching, name='ご注文はうさぎですか？'))
                    self.channel_id = []
                    return True
                else:
                    return False
            case 'insert':
                return True if len(self.bot.voice_clients) != 0 else False
            case _:
                logger.critical('A unknown error has occurred!')

    async def change_status(self, act) -> None:
        await self.bot.change_presence(activity=act, status=discord.Status.online)

    def clean(self, _: discord.Interaction) -> int:
        try:
            for file in os.scandir(self.song_path):
                if file.path[-4:] == '.mp3':
                    os.remove(file.path)
        except PermissionError as e:
            logger.error(e)
            logger.error('ffmpeg is possible that there is no normal exit!')
            return 1
        return 0


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(YotubePlayer(bot), guild=None)
