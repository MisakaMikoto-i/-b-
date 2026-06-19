import re
import json
import httpx
from .base import BaseParser, Song


class KugouParser(BaseParser):
    @staticmethod
    def can_parse(url: str) -> bool:
        return "kugou.com" in url

    @staticmethod
    async def parse(url: str) -> list[Song]:
        playlist_id = None
        match = re.search(r'id=(\d+)', url)
        if match:
            playlist_id = match.group(1)
        match = re.search(r'playlist[/#](\d+)', url)
        if match:
            playlist_id = match.group(1)
        match = re.search(r'/(\d+)(?:\.html|\?|$)', url)
        if match and not playlist_id:
            playlist_id = match.group(1)

        if not playlist_id:
            return await KugouParser._parse_share_url(url)

        return await KugouParser._fetch_playlist(playlist_id)

    @staticmethod
    async def _parse_share_url(url: str) -> list[Song]:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(url, timeout=30)
            text = resp.text
            match = re.search(r'globalData\s*=\s*(\{.*?\});', text, re.DOTALL)
            if match:
                data = json.loads(match.group(1))
                playlist_id = data.get("mixId") or data.get("specialId") or data.get("id")
                if playlist_id:
                    return await KugouParser._fetch_playlist(str(playlist_id))
        raise ValueError("无法解析酷狗歌单链接")

    @staticmethod
    async def _fetch_playlist(playlist_id: str) -> list[Song]:
        url = f"https://mobilecdn.kugou.com/api/v5/special/song"
        params = {
            "specialid": playlist_id,
            "page": 1,
            "pagesize": 300,
            "plat": 2,
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()

        info = data.get("data", {})
        songs_data = info.get("info", [])

        songs = []
        for track in songs_data:
            song_name = track.get("songname", "")
            song_name = re.sub(r'<[^>]+>', '', song_name)
            singer = track.get("singername", track.get("author_name", ""))
            duration = track.get("duration", 0)
            songs.append(
                Song(
                    name=song_name,
                    artist=singer,
                    duration=duration,
                    platform_id=str(track.get("hash", "")),
                )
            )
        return songs
