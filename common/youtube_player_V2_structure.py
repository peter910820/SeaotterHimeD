from typing import TypedDict


class SongDetails(TypedDict):
    '''
    播放佇列內每一筆音樂的的型別定義
    '''

    url: str
    title: str
