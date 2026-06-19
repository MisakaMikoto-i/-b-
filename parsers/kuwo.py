import re
import httpx
from .base import BaseParser, Song


class KuwoParser(BaseParser):
    @staticmethod
    def can_parse(url: str) -> bool:
        return "kuwo.cn" in url

    @staticmethod
    async def parse(url: str) -> list[Song]:
        playlist_id = None
        match = re.search(r'id=(\d+)', url)
        if match:
            playlist_id = match.group(1)
        match = re.search(r'playlist/(\d+)', url)
        if match:
            playlist_id = match.group(1)
        match = re.search(r'/(\d+)(?:\.html|\?|$)', url)
        if match and not playlist_id:
            playlist_id = match.group(1)

        if not playlist_id:
            raise ValueError("无法从URL中提取酷我歌单ID")

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.kuwo.cn/",
        }

        api_url = f"https://www.kuwo.cn/api/www/playlist/playListInfo"
        params = {"pid": playlist_id, "pn": 1, "rn": 300, "httpsStatus": 1}

        async with httpx.AsyncClient() as client:
            resp = await client.get(api_url, params=params, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()

        music_list = data.get("data", {}).get("musicList", [])
        songs = []
        for track in music_list:
            artist = track.get("artist", "")
            duration = int(track.get("duration", 0))
            songs.append(
                Song(
                    name=track.get("name", ""),
                    artist=artist,
                    album=track.get("album", ""),
                    duration=duration,
                    platform_id=str(track.get("rid", "")),
                )
            )
        return songs
