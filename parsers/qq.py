import re
import json
import httpx
from .base import BaseParser, Song


QQ_PLAYLIST_API = "https://c.y.qq.com/qzone/fcg-bin/fcg_ucc_getcdinfo_byids_cp.fcg"


class QQParser(BaseParser):
    @staticmethod
    def can_parse(url: str) -> bool:
        return "qq.com" in url and (
            "y.qq.com" in url
            or "playlist" in url
            or "c6.y.qq.com" in url
            or "/u?" in url
        )

    @staticmethod
    async def parse(url: str, qq_cookie: dict | None = None) -> list[Song]:
        playlist_id = QQParser._extract_id(url)

        if not playlist_id:
            url = await QQParser._resolve_short_link(url)
            playlist_id = QQParser._extract_id(url)

        if not playlist_id:
            raise ValueError("无法从URL中提取QQ音乐歌单ID")

        songs = await QQParser._fetch_via_qzone_api(playlist_id, qq_cookie)
        if songs:
            return songs

        songs = await QQParser._fetch_via_musicu(playlist_id, qq_cookie)
        if songs:
            return songs

        if qq_cookie:
            songs = await QQParser._fetch_via_playwright(playlist_id, qq_cookie)
            if songs:
                return songs

        raise ValueError("未找到QQ音乐歌单内容（可能是私有歌单，请登录QQ音乐后重试）")

    @staticmethod
    async def _fetch_via_qzone_api(playlist_id: str, qq_cookie: dict | None = None) -> list[Song]:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://y.qq.com/",
        }
        if qq_cookie:
            headers["Cookie"] = f"uin=o0{qq_cookie['uin']}; qqmusic_key={qq_cookie['qqmusic_key']}; qm_keyst={qq_cookie['qqmusic_key']}"

        params = {
            "type": 1, "json": 1, "utf8": 1, "onlysong": 0,
            "new_format": 1, "disstid": playlist_id,
            "platform": "yqq.json", "needNewCode": 0,
        }

        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                resp = await client.get(QQ_PLAYLIST_API, params=params, headers=headers, timeout=30)
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
                return []

            songlist = cdlist[0].get("songlist", [])
            return QQParser._parse_songlist(songlist)
        except Exception:
            return []

    @staticmethod
    async def _fetch_via_musicu(playlist_id: str, qq_cookie: dict | None = None) -> list[Song]:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://y.qq.com/",
        }
        if qq_cookie:
            headers["Cookie"] = f"uin=o0{qq_cookie['uin']}; qqmusic_key={qq_cookie['qqmusic_key']}; qm_keyst={qq_cookie['qqmusic_key']}"

        data = {
            "comm": {"ct": 24, "cv": 0},
            "playlist": {
                "method": "get_playlist",
                "module": "playlist.PlayListPlazaSvr",
                "param": {"id": int(playlist_id), "offset": 0, "num": 300}
            }
        }

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post("https://u.y.qq.com/cgi-bin/musicu.fcg", json=data, headers=headers, timeout=30)
                result = resp.json()

            playlist_data = result.get("playlist", {})
            if playlist_data.get("code") != 0:
                return []

            songlist = playlist_data.get("data", {}).get("songlist", [])
            return QQParser._parse_songlist(songlist)
        except Exception:
            return []

    @staticmethod
    async def _fetch_via_playwright(playlist_id: str, qq_cookie: dict) -> list[Song]:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()

            await context.add_cookies([
                {"name": "uin", "value": f"o0{qq_cookie['uin']}", "domain": ".qq.com", "path": "/"},
                {"name": "qqmusic_key", "value": qq_cookie["qqmusic_key"], "domain": ".qq.com", "path": "/"},
                {"name": "qm_keyst", "value": qq_cookie["qqmusic_key"], "domain": ".qq.com", "path": "/"},
            ])

            page = await context.new_page()

            collected_songs = []

            async def handle_response(response):
                url = response.url
                if "musics.fcg" in url and response.status == 200:
                    try:
                        body = await response.body()
                        text = body.decode("utf-8", errors="replace")
                        if "songlist" in text or "songname" in text:
                            data = json.loads(text)
                            songlist = data.get("songlist", [])
                            if songlist:
                                collected_songs.extend(QQParser._parse_songlist(songlist))
                    except Exception:
                        pass

            page.on("response", handle_response)

            try:
                await page.goto(
                    f"https://y.qq.com/n/ryqq_v2/playlist/{playlist_id}",
                    wait_until="domcontentloaded",
                    timeout=20000,
                )
                await page.wait_for_timeout(12000)
            except Exception:
                pass

            if not collected_songs:
                try:
                    dom_songs = await page.evaluate("""() => {
                        const items = document.querySelectorAll('.songlist__item, [class*="song_item"]');
                        const results = [];
                        items.forEach(item => {
                            const nameEl = item.querySelector('.songlist__songname, [class*="songname"]');
                            const artistEl = item.querySelector('.songlist__artist, [class*="singer"]');
                            if (nameEl) {
                                results.push({
                                    name: nameEl.textContent.trim(),
                                    artist: artistEl ? artistEl.textContent.trim() : ''
                                });
                            }
                        });
                        return results;
                    }""")
                    for s in dom_songs:
                        collected_songs.append(Song(name=s["name"], artist=s["artist"]))
                except Exception:
                    pass

            await browser.close()

        return collected_songs

    @staticmethod
    def _parse_songlist(songlist: list) -> list[Song]:
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
    async def _resolve_short_link(url: str) -> str:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(url, headers=headers, timeout=15)
            return str(resp.url)

    @staticmethod
    def _extract_id(url: str) -> str | None:
        patterns = [
            r'id=(\d+)',
            r'playlist[/#](\d+)',
            r'/(\d+)(?:\.html|\?|$)',
        ]
        for p in patterns:
            m = re.search(p, url)
            if m:
                return m.group(1)
        return None
