import re


def normalize(text: str) -> str:
    text = re.sub(r'[\(\（【\[（feat\.?|ft\.?|with).*?[\)\）】\]]', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s+', ' ', text).strip()
    text = text.lower()
    replacements = {
        '（': '(', '）': ')', '【': '[', '】': ']',
        '：': ':', '，': ',', '、': ',',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def match_score(song_name: str, song_artist: str, video_title: str, video_duration: int = 0, song_duration: int = 0) -> float:
    score = 0.0
    title_lower = video_title.lower()
    name_norm = normalize(song_name)
    artist_norm = normalize(song_artist)

    if name_norm in title_lower:
        score += 15
    elif len(name_norm) >= 3:
        words = [w for w in name_norm.split() if len(w) >= 2]
        matched_words = sum(1 for w in words if w in title_lower)
        if words and matched_words == len(words):
            score += 12
        elif words and matched_words > 0:
            score += int(matched_words / len(words) * 8)

    if artist_norm:
        if artist_norm in title_lower:
            score += 8
        else:
            artist_parts = artist_norm.replace("/", " ").replace(",", " ").split()
            matched = sum(1 for p in artist_parts if p in title_lower and len(p) > 1)
            if matched > 0:
                score += matched * 3

    hires_keywords = ["hi-res", "hires", "hi_res", "无损", "flac", "lossless", "高品质", "hd"]
    for kw in hires_keywords:
        if kw in title_lower:
            score += 10
            break

    quality_keywords = ["官方", "mv", "音源", "4k", "超清", "高清"]
    for kw in quality_keywords:
        if kw in title_lower:
            score += 2
            break

    if video_duration > 0 and song_duration > 0:
        diff = abs(video_duration - song_duration)
        if diff <= 10:
            score += 3
        elif diff <= 30:
            score += 1

    return score


def is_hires(title: str, description: str = "") -> bool:
    text = (title + " " + description).lower()
    keywords = ["hi-res", "hires", "hi_res", "无损", "flac", "lossless"]
    return any(kw in text for kw in keywords)
