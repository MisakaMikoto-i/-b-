import re


def normalize(text: str) -> str:
    text = re.sub(r'[\(\（【\[](.*?(?:feat\.?|ft\.?|with).*?)[\)\）】\]]', '', text, flags=re.IGNORECASE)
    text = re.sub(r'[\(\（【\[].*?[\)\）】\]]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    text = text.lower()
    replacements = {
        '（': '(', '）': ')', '【': '[', '】': ']',
        '：': ':', '，': ',', '、': ',',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def _extract_version_keywords(text: str) -> set[str]:
    brackets = re.findall(r'[\(\（【\[](.*?)[\)\）】\]]', text, flags=re.IGNORECASE)
    keywords = set()
    for content in brackets:
        for word in re.split(r'[\s,/&]+', content.lower()):
            word = word.strip('. ')
            if word:
                keywords.add(word)
    return keywords


SPEED_PATTERN = re.compile(
    r'(?:\b\d+(?:\.\d+)?x\b|'
    r'\bslowed\b|\bsped\s*up\b|\bnightcore\b|'
    r'加速|减速|变速|倍速)',
    re.IGNORECASE
)

BAD_VERSION_KW = ["live", "现场", "演唱会", "翻唱", "cover", "搬运", "remix", "改编"]
BAD_VERSION_KW2 = ["剪辑", "片段", "铃声"]
ACCOMPANIMENT_KW = ["伴奏", "instrumental", "纯音乐", "bgm", "卡拉ok", "k歌"]
HIRES_KW = ["hi-res", "hires", "hi_res", "无损", "flac", "lossless", "高品质", "hd"]
GOOD_KW = ["官方", "音源", "mv", "完整版"]


def match_score(song_name: str, song_artist: str, video_title: str, video_duration: int = 0, song_duration: int = 0) -> float:
    score = 0.0
    title_lower = video_title.lower()
    name_norm = normalize(song_name)
    artist_norm = normalize(song_artist)
    song_version_kw = _extract_version_keywords(song_name)

    song_has_acc = any(kw in name_norm for kw in ACCOMPANIMENT_KW)
    video_has_acc = any(kw in title_lower for kw in ACCOMPANIMENT_KW)
    if video_has_acc and not song_has_acc:
        return -100

    name_ok = False
    if name_norm in title_lower:
        score += 15
        name_ok = True
    elif len(name_norm) <= 2:
        return -100
    elif len(name_norm) >= 3:
        words = [w for w in name_norm.split() if len(w) >= 2]
        matched_words = sum(1 for w in words if w in title_lower)
        if words and matched_words == len(words):
            score += 12
            name_ok = True
        elif words and matched_words > 0:
            ratio = matched_words / len(words)
            score += int(ratio * 8)
            if ratio >= 0.5:
                name_ok = True

    if not name_ok:
        return -100

    if artist_norm:
        if artist_norm in title_lower:
            score += 8
        else:
            artist_parts = artist_norm.replace("/", " ").replace(",", " ").split()
            matched = sum(1 for p in artist_parts if p in title_lower and len(p) > 1)
            if matched > 0:
                score += matched * 3

    for kw in HIRES_KW:
        if kw in title_lower:
            score += 5
            break

    for kw in GOOD_KW:
        if kw in title_lower:
            score += 5
            break

    for kw in BAD_VERSION_KW:
        if kw in title_lower and kw not in song_version_kw:
            score -= 8
            break

    for kw in BAD_VERSION_KW2:
        if kw in title_lower and kw not in song_version_kw:
            score -= 5
            break

    if SPEED_PATTERN.search(video_title) and not SPEED_PATTERN.search(song_name):
        score -= 15

    if video_duration > 0 and song_duration > 0:
        diff = abs(video_duration - song_duration)
        if diff > 120:
            return -100
        elif diff > 60:
            score -= 10
        elif diff <= 10:
            score += 5
        elif diff <= 30:
            score += 1

    return score


def is_hires(song_name: str, video_title: str, description: str = "") -> bool:
    name_norm = normalize(song_name)
    title_lower = video_title.lower()
    if name_norm not in title_lower:
        words = [w for w in name_norm.split() if len(w) >= 2]
        if not (words and all(w in title_lower for w in words)):
            return False
    text = (video_title + " " + description).lower()
    return any(kw in text for kw in HIRES_KW)
