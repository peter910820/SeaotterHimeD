import asyncio
import discord
import os
import re
import yt_dlp

from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from loguru import logger
from typing import Optional, TypedDict, cast

from common.structure import CustomError
from common.youtube_player_V2_structure import SongDetails
from utils.embed_output import error_output, youtube_palyer_output, youtube_palyer_notice_output


load_dotenv()


class PostprocessorsOptions(TypedDict):
    '''
    解析音檔的型別定義
    '''

    key: str
    preferredcodec: str
    preferredquality: str


class YoutubeDLOptions(TypedDict):
    '''
    YoutubeDL播放參數的型別定義
    '''

    cookiefile: str
    format: str
    outtmpl: str
    postprocessors: list[PostprocessorsOptions]


class YoutubeDLOptionsForList(TypedDict):
    '''
    YoutubeDL播放參數(清單)的型別定義
    '''

    cookiefile: str
    extract_flat: bool  # dont download
    quiet: bool  # undisplay progress bar
    noplaylist: bool  # playlist


class YotubePlayerV2(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

        FFMPEG_PATH = os.getenv('FFMPEG_PATH')
        if FFMPEG_PATH == None:
            raise CustomError(f'load .env file parameter "FFMPEG_PATH" failed')
        self.ffmpeg_path = FFMPEG_PATH

        self.forbidden_char = re.compile(r'[/\\:*?"\'<>|\.]')
        self.play_list: list[SongDetails] = []
        self.channel_id: list[int] = []
        self.text_channel_id = None
        self.pause_flag: bool = False
        self.song_path: str = './music_tmp/'
        self.cookie_path: str = './cookies.txt'
        self.volume: float = 0.1
        self.notice: bool = False
        self.get_details_options: YoutubeDLOptionsForList = {
            'cookiefile': self.cookie_path,
            'extract_flat': True,  # dont download
            'quiet': True,  # undisplay progress bar
            'noplaylist': False,  # playlist
        }
        self.ydl_opts_postprocessors: list[PostprocessorsOptions] = [{
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
            case _:
                raise CustomError(
                    f'no usage of parameter c_var="{c_var}"')
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
            await asyncio.sleep(1)
            self.clean(interaction)
            await interaction.response.send_message(embed=await youtube_palyer_output('離開語音頻道成功'))
        else:
            await interaction.response.send_message(embed=await youtube_palyer_output('機器人未加入頻道'))

    @app_commands.command(name='play', description='播放YT音樂')
    @app_commands.describe(notice='song notice, if not entered, Bot doesn\'t notify when song changes',
                           channel_id='Voice channel id, if not entered, the current channel will be used')
    @app_commands.choices(notice=[
        app_commands.Choice(name='False', value=0),
        app_commands.Choice(name='True', value=1),
    ])
    async def play(self, interaction: discord.Interaction, notice: int, youtube_url: str, channel_id: str = '0') -> None:
        self.notice = bool(notice)
        self.text_channel_id = interaction.channel
        await interaction.response.defer()
        youtube_url = self.url_format(youtube_url)
        if youtube_url == 'None':
            await interaction.followup.send(embed=await youtube_palyer_output('找不到歌曲喔'))
            return
        if await self.handle_connect(interaction, 'play', channel_id):
            try:
                await self.get_details(youtube_url)

                voice_clients = self.__type_check(
                    self.bot.voice_clients[0])  # check type
                if not voice_clients.is_playing():
                    await interaction.followup.send(embed=await youtube_palyer_output(f'歌曲/單已加入: 加入網址為{youtube_url} 即將開始播放歌曲~'))
                    music_path = await self.download_song(0)  # download music
                    source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(
                        executable=self.ffmpeg_path, source=f'{music_path}.mp3'), volume=self.volume)
                    voice_clients.play(
                        source, after=lambda error: self.after_song_interface(
                            interaction, error)
                    )
                    if self.notice:
                        await interaction.followup.send(embed=await youtube_palyer_notice_output(self.play_list[0]))
                    await self.change_status(discord.Activity(
                        type=discord.ActivityType.listening, name=self.play_list[0]['title']))
                    if len(self.play_list) - 1 >= 1:
                        # download music
                        music_path = await self.download_song(1)
                else:
                    await interaction.followup.send(embed=await youtube_palyer_output(f'歌曲已加入排序: 加入網址為{youtube_url}'))
                    if len(self.play_list) - 1 >= 1 and not os.path.exists(f'{self.song_path}{self.play_list[1]["title"]}.mp3'):
                        # download music
                        music_path = await self.download_song(1)

            except Exception as e:
                logger.error(e)
                await interaction.followup.send(embed=await error_output(e))
                return
        else:
            await interaction.followup.send(embed=await youtube_palyer_output('加入頻道失敗/未加入頻道'))

    def after_song_interface(self, interaction: discord.Interaction, error: Optional[Exception]):
        if error:
            logger.error(str(error))
        else:
            logger.debug(str(error))
            self.bot.loop.create_task(self.after_song(interaction))

    async def download_song(self, index: int) -> str:
        try:
            title = self.forbidden_char.sub(
                '_', self.play_list[index]['title'])
            self.play_list[index]['title'] = title
            url = self.play_list[index]['url']
            music_path = f'{self.song_path}{title}'
            ydl_opts: YoutubeDLOptions = {
                'cookiefile': self.cookie_path,
                'format': 'bestaudio/best',
                'outtmpl': music_path,
                'postprocessors': self.ydl_opts_postprocessors,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            return music_path
        except Exception as e:
            logger.error(e)
            raise CustomError(str(e))

    async def after_song(self, interaction: discord.Interaction):
        previous_song = f'{self.song_path}{self.play_list[0]["title"]}.mp3'
        # judgment self.text_channel_id type is correct
        if not isinstance(self.text_channel_id, discord.TextChannel):
            raise CustomError('self.text_channel_id is not a TextChannel')

        self.clean_single(interaction, previous_song)
        if len(self.bot.voice_clients) == 0:
            logger.warning('Reconnection failed, bot is ready to exit...')
            self.play_list.clear()
            self.clean(interaction)
            await self.text_channel_id.send(embed=await youtube_palyer_output('機器人連線失敗，請稍後再使用'))
            self.channel_id.clear()
            return
        if len(self.play_list) > 0:
            self.play_list.pop(0)
            previous_song = f'{self.song_path}{self.play_list[0]["title"]}.mp3'
            # check if song exists
            if os.path.exists(previous_song):
                music_path = f'{self.song_path}{self.play_list[0]["title"]}'
            else:
                music_path = await self.download_song(0)  # download music

            voice_clients = self.__type_check(
                self.bot.voice_clients[0])  # check type

            source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(
                executable=self.ffmpeg_path, source=f'{music_path}.mp3'), volume=self.volume)
            voice_clients.play(
                source, after=lambda error: self.after_song_interface(
                    interaction, error)
            )
            if self.notice:
                await self.text_channel_id.send(embed=await youtube_palyer_notice_output(self.play_list[0]))
            await self.change_status(discord.Activity(
                type=discord.ActivityType.listening, name=self.play_list[0]['title']))
            if len(self.play_list) - 1 >= 1:
                music_path = await self.download_song(1)  # download music
        else:
            await self.change_status(discord.Activity(
                type=discord.ActivityType.watching, name='Galgame'))
            logger.success('已播放完歌曲')
            await self.text_channel_id.send(embed=await youtube_palyer_output('已播放完歌曲'))
            self.channel_id.clear()

    @app_commands.command(name='skip', description='跳過歌曲')
    async def skip(self, interaction: discord.Interaction, count: int = 1) -> None:
        await interaction.response.defer()
        previous_song = f'{self.song_path}{self.play_list[0]["title"]}.mp3'
        song_length = len(self.play_list)
        if song_length == 0:
            await interaction.followup.send(embed=await youtube_palyer_output('我還沒加入語音頻道呦'))
            return
        if count > 1:
            if count > song_length:
                count = song_length
            count -= 1
            for _ in range(0, count):
                self.play_list.pop(0)
        voice_clients = self.__type_check(
            self.bot.voice_clients[0])  # check type
        voice_clients.stop()
        await asyncio.sleep(5)  # make sure ffmpeg is stop
        if count + 1 > 1:
            now_song = f'{self.song_path}{self.play_list[0]["title"]}.mp3'
            pre_song = f'{self.song_path}{self.play_list[1]["title"]}.mp3'
            self.__clean_specify(interaction, now_song, pre_song)
        else:
            self.clean_single(interaction, previous_song)
        await interaction.followup.send(embed=await youtube_palyer_output('歌曲已跳過'))

    @app_commands.command(name='pause', description='暫停歌曲')
    async def pause(self, interaction: discord.Interaction) -> None:
        voice_clients = self.__type_check(
            self.bot.voice_clients[0])  # check type
        if voice_clients.is_playing():
            voice_clients.pause()
            self.pause_flag = True
            await interaction.response.send_message(embed=await youtube_palyer_output('歌曲已暫停'))
        else:
            await interaction.response.send_message(embed=await youtube_palyer_output('沒有歌曲正在播放'))

    @app_commands.command(name='resume', description='回復播放歌曲')
    async def resume(self, interaction: discord.Interaction) -> None:
        voice_clients = self.__type_check(
            self.bot.voice_clients[0])  # check type
        if voice_clients.is_paused():
            voice_clients.resume()
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
                            self.play_list.insert(
                                1, {'url': youtube_url, 'title': details.get('title')})
                            logger.info(self.play_list[1])
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
        if len(self.play_list) == 0:
            await interaction.followup.send(embed=await youtube_palyer_output('播放清單目前為空'))
        else:
            display = f'播放清單剩餘歌曲: {len(self.play_list)}首\n :arrow_forward: '
            for index, t in enumerate(self.play_list, start=1):
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
            self.play_list.extend(song_details)

    def url_format(self, youtube_url: str) -> str:
        if '&list=' in youtube_url:  # remove '&list=' tag
            youtube_url = youtube_url[0:youtube_url.find('&list=')]
        if youtube_url.startswith(('https://www.youtube.com/', 'https://youtube.com/', 'https://youtu.be/')):
            return youtube_url
        # handle youtube music
        elif youtube_url.startswith('https://music.youtube.com/'):
            return youtube_url.replace('music', 'www')
        else:  # this is not a correct link
            return 'None'

    async def handle_connect(self, interaction: discord.Interaction, command: str, channel_id: str | int = '') -> bool:
        match command:
            case 'join' | 'play':
                try:
                    channel_id = int(channel_id)  # try parse to int
                except ValueError:
                    logger.error('請輸入正確的channel_id!')
                    return False
                if len(self.bot.voice_clients) == 0:
                    if cast(discord.Member, interaction.user).voice != None or channel_id != 0:
                        if channel_id == 0:
                            voice_channel = cast(
                                discord.Member, interaction.user).voice.channel
                        else:
                            voice_channel = self.bot.get_channel(
                                cast(int, channel_id))
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
                    if len(self.play_list) != 0:
                        try:
                            voice_clients = self.__type_check(
                                self.bot.voice_clients[0])  # check type
                            self.play_list = [self.play_list[0]]
                            voice_clients.stop()
                        except:
                            return True
                        await asyncio.sleep(1)  # Ensures the stop is complete
                    await self.bot.voice_clients[0].disconnect(force=False)
                    await self.change_status(discord.Activity(
                        type=discord.ActivityType.playing, name='Galgame'))
                    self.channel_id = []
                    return True
                else:
                    return False
            case 'insert':
                return True if len(self.bot.voice_clients) != 0 else False
            case _:
                raise CustomError(
                    f'encountered an incorrect command \'{command}\'')

    async def change_status(self, act: discord.Activity) -> None:
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

    def clean_single(self, _: discord.Interaction, song_route: str) -> int:
        try:
            if os.path.exists(song_route):
                os.remove(song_route)
        except PermissionError as e:
            logger.error(e)
            return 1
        return 0

    def __clean_specify(self, _: discord.Interaction, now_song_route: str, pre_song_route: str) -> int:
        try:
            for file in os.scandir(self.song_path):
                if file.path[-4:] == '.mp3' and (file.path != now_song_route and file.path != pre_song_route):
                    os.remove(file.path)
        except PermissionError as e:
            logger.error(e)
            logger.error('ffmpeg is possible that there is no normal exit!')
            return 1
        return 0

    def __type_check(self, voice_clients: discord.VoiceProtocol) -> discord.VoiceClient:
        if not isinstance(voice_clients, discord.VoiceClient):
            raise CustomError('voice_clients is not a discord.VoiceClient')
        return voice_clients


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(YotubePlayerV2(bot), guild=None)
