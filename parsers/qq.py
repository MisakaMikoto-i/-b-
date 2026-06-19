import re
import json
import httpx
from .base import BaseParser, Song


QQ_PLAYLIST_API = "https://c.y.qq.com/qzone/fcg-bin/fcg_ucc_getcdinfo_byids_cp.fcg"


class QQParser(BaseParser):
    @staticmethod
    def can_parse(url: str) -> bool:
        return "y.qq.com" in url or ("qq.com" in url and "playlist" in url)

    @staticmethod
    async def parse(url: str) -> list[Song]:
        playlist_id = QQParser._extract_id(url)
        if not playlist_id:
            raise ValueError("无法从URL中提取QQ音乐歌单ID")

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://y.qq.com/",
        }
        params = {
            "type": 1,
            "json": 1,
            "utf8": 1,
            "onlysong": 0,
            "new_format": 1,
            "disstid": playlist_id,
            "platform": "yqq.json",
            "needNewCode": 0,
        }

        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(QQ_PLAYLIST_API, params=params, headers=headers, timeout=30)
            resp.raise_for_status()
            text = resp.text

        if text.startswith("jsonCallback("):
            text = text[len("jsonCallback("):]
            if text.endswith(")"):
                text = text[:-1]
            elif text.endswith(");"):
                text = text[:-2]

        data = json.loads(text)
        cdlist = data.get("cdlist", [])
        if not cdlist:
            raise ValueError("未找到QQ音乐歌单内容")

        songlist = cdlist[0].get("songlist", [])
        songs = []
        for track in songlist:
            singers = "/".join(
                s.get("name", "") for s in track.get("singer", [])
            )
            album_name = track.get("album", {}).get("name", track.get("albumname", ""))
            interval = track.get("interval", 0)
            songs.append(
                Song(
                    name=track.get("name", track.get("songname", "")),
                    artist=singers,
                    album=album_name,
                    duration=interval,
                    platform_id=str(track.get("songmid", track.get("mid", ""))),
                )
            )
        return songs

    @staticmethod
    def _extract_id(url: str) -> str | None:
        patterns = [
            r'id=(\d+)',
            r'playlist[/#](\d+)',
            r'/(\d+)(?:\.html|$)',
        ]
        for p in patterns:
            m = re.search(p, url)
            if m:
                return m.group(1)
        return None
