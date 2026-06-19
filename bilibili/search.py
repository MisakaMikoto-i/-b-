import asyncio
import re
from bilibili_api import search
from utils.matcher import match_score, is_hires
from parsers.base import Song


def _clean_title(title: str) -> str:
    return re.sub(r'<[^>]+>', '', title)


def _parse_duration(dur_str: str) -> int:
    parts = dur_str.split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        else:
            return int(parts[0])
    except (ValueError, IndexError):
        return 0


async def _do_search(keyword: str, page_size: int = 30) -> list[dict]:
    for attempt in range(2):
        try:
            result = await search.search_by_type(
                keyword=keyword,
                search_type=search.SearchObjectType.VIDEO,
                order_type=search.OrderVideo.TOTALRANK,
                page=1,
                page_size=page_size,
            )
            return result.get("result", [])
        except Exception:
            if attempt == 0:
                await asyncio.sleep(2)
    return []


def _build_match(r: dict, song: Song, score: float) -> dict:
    title = _clean_title(r.get("title", ""))
    dur = _parse_duration(r.get("duration", "0:00"))
    bvid = r.get("bvid", "")
    aid = r.get("aid", r.get("id", 0))
    description = r.get("description", "")
    tag = r.get("tag", "")
    return {
        "bvid": bvid,
        "aid": aid,
        "title": title,
        "duration": dur,
        "score": score,
        "hires": is_hires(song.name, title, description + " " + tag),
        "play": r.get("play", 0),
        "author": r.get("author", ""),
    }


async def search_top_matches(song: Song, top_n: int = 3) -> list[dict]:
    queries = [
        f"{song.name} {song.artist}",
        song.name,
    ]

    all_results = []
    for query in queries:
        results = await _do_search(query)
        if results:
            all_results.extend(results)
            if len(all_results) >= 30:
                break
        await asyncio.sleep(0.5)

    if not all_results:
        return []

    seen_bvids = set()
    unique_results = []
    for r in all_results:
        bvid = r.get("bvid", "")
        if bvid and bvid not in seen_bvids:
            seen_bvids.add(bvid)
            unique_results.append(r)

    scored = []
    for r in unique_results:
        title = _clean_title(r.get("title", ""))
        dur = _parse_duration(r.get("duration", "0:00"))
        score = match_score(song.name, song.artist, title, dur, song.duration)

        author = r.get("author", "")
        if song.artist and song.artist.lower() in author.lower():
            score += 5

        play_count = r.get("play", 0)
        if isinstance(play_count, str):
            try:
                play_count = int(play_count.replace(",", ""))
            except ValueError:
                play_count = 0
        if play_count > 1000000:
            score += 5
        elif play_count > 100000:
            score += 3
        elif play_count > 10000:
            score += 1

        scored.append((score, r, title, dur))

    scored.sort(key=lambda x: x[0], reverse=True)

    matches = []
    for score_val, r, title, dur in scored[:top_n]:
        if score_val < 5:
            break
        matches.append(_build_match(r, song, score_val))

    return matches


async def search_best_match(song: Song) -> dict | None:
    matches = await search_top_matches(song, top_n=1)
    return matches[0] if matches else None


async def search_songs(songs: list[Song], concurrency: int = 2, progress_callback=None) -> list[dict]:
    total = len(songs)
    done_count = 0
    sem = asyncio.Semaphore(concurrency)

    async def _search_one(idx: int, song: Song):
        nonlocal done_count
        async with sem:
            try:
                matches = await search_top_matches(song, top_n=3)
                result = matches[0] if matches else None
            except Exception:
                matches = []
                result = None
            done_count += 1
            if progress_callback:
                await progress_callback(done_count, total, song.name, result is not None)
            return {"index": idx, "song": song, "match": result, "candidates": matches}

    tasks = [_search_one(i, song) for i, song in enumerate(songs)]
    results = await asyncio.gather(*tasks)

    results = list(results)
    results.sort(key=lambda x: x.get("index", 0))
    return results
