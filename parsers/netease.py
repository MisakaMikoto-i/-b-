import re
import httpx
from .base import BaseParser, Song
from config import NETEASE_API


class NetEaseParser(BaseParser):
    @staticmethod
    def can_parse(url: str) -> bool:
        return "music.163.com" in url or "163.cn" in url

    @staticmethod
    async def parse(url: str) -> list[Song]:
        match = re.search(r'id=(\d+)', url)
        if not match:
            match = re.search(r'playlist/(\d+)', url)
        if not match:
            raise ValueError("无法从URL中提取网易云歌单ID")
        playlist_id = match.group(1)

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://music.163.com/",
        }
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                NETEASE_API,
                params={"id": playlist_id, "n": 100000},
                headers=headers,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

        playlist = data.get("playlist") or data.get("result", {})
        tracks = playlist.get("tracks", [])
        track_ids = playlist.get("trackIds", [])

        if len(track_ids) > len(tracks):
            all_ids = [t["id"] for t in track_ids]
            return await NetEaseParser._fetch_tracks_detail(all_ids, headers)

        songs = []
        for track in tracks:
            artists = "/".join(
                a.get("name", "") for a in track.get("ar", track.get("artists", []))
            )
            album_name = (track.get("al") or track.get("album", {})).get("name", "")
            songs.append(
                Song(
                    name=track.get("name", ""),
                    artist=artists,
                    album=album_name,
                    duration=track.get("dt", 0) // 1000,
                    platform_id=str(track.get("id", "")),
                )
            )
        return songs

    @staticmethod
    async def _fetch_tracks_detail(track_ids: list[int], headers: dict) -> list[Song]:
        songs = []
        batch_size = 200
        detail_url = "https://music.163.com/api/v3/song/detail"

        async with httpx.AsyncClient() as client:
            for i in range(0, len(track_ids), batch_size):
                batch = track_ids[i : i + batch_size]
                c_param = str([{"id": tid} for tid in batch])
                resp = await client.post(
                    detail_url,
                    data={"c": c_param},
                    headers=headers,
                    timeout=30,
                )
                resp.raise_for_status()
                data = resp.json()

                for track in data.get("songs", []):
                    artists = "/".join(a.get("name", "") for a in track.get("ar", []))
                    album_name = (track.get("al") or {}).get("name", "")
                    songs.append(
                        Song(
                            name=track.get("name", ""),
                            artist=artists,
                            album=album_name,
                            duration=track.get("dt", 0) // 1000,
                            platform_id=str(track.get("id", "")),
                        )
                    )

        return songs
