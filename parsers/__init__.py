import re
from .base import BaseParser, Song
from .netease import NetEaseParser
from .qq import QQParser
from .kugou import KugouParser
from .kuwo import KuwoParser

PARSERS: list[type[BaseParser]] = [
    NetEaseParser,
    QQParser,
    KugouParser,
    KuwoParser,
]


async def parse_playlist(url: str) -> list[Song]:
    for parser in PARSERS:
        if parser.can_parse(url):
            return await parser.parse(url)
    raise ValueError(f"不支持的歌单链接: {url}")
