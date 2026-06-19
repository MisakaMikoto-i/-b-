import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CREDENTIAL_FILE = BASE_DIR / "credential.json"

BILIBILI_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com",
}

NETEASE_API = "https://music.163.com/api/v6/playlist/detail"
QQ_PLAYLIST_API = "https://c.y.qq.com/v8/fcg-bin/fcg_v8_playlist_cp.fcg"
KUGOU_SEARCH_API = "https://mobilecdn.kugou.com/api/v3/search/song"
KUWO_API = "https://www.kuwo.cn/api/www/classify/playlist/getPlayListInfoByPage"

REQUEST_DELAY = 0.5
