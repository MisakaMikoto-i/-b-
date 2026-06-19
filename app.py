import asyncio
import json
import uuid
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from parsers import parse_playlist
from bilibili.auth import load_credential, create_credential_from_manual, clear_credential
from bilibili.search import search_top_matches
from bilibili.collector import create_favorite, batch_add_to_favorite, get_user_info
from parsers.base import Song
from config import BASE_DIR

app = FastAPI(title="歌单转BV收藏夹")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

tasks: dict[str, dict] = {}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    credential = load_credential()
    logged_in = credential is not None
    user_info = None
    if logged_in:
        try:
            user_info = await get_user_info(credential)
        except Exception:
            logged_in = False
            credential = None
    return templates.TemplateResponse(request, "index.html", {
        "logged_in": logged_in,
        "user_info": user_info,
    })


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    credential = load_credential()
    logged_in = credential is not None
    return templates.TemplateResponse(request, "login.html", {
        "logged_in": logged_in,
    })


@app.post("/login/manual")
async def login_manual(
    sessdata: str = Form(...),
    bili_jct: str = Form(""),
    buvid3: str = Form(""),
):
    try:
        cred = create_credential_from_manual(sessdata, bili_jct, buvid3)
        await get_user_info(cred)
        return RedirectResponse("/", status_code=303)
    except Exception as e:
        return JSONResponse({"error": f"登录失败: {str(e)}"}, status_code=400)


@app.post("/logout")
async def logout():
    clear_credential()
    return RedirectResponse("/", status_code=303)


@app.post("/parse", response_class=JSONResponse)
async def parse(request: Request):
    body = await request.json()
    url = body.get("url", "").strip()
    if not url:
        return JSONResponse({"error": "请输入歌单链接"}, status_code=400)

    try:
        songs = await parse_playlist(url)
    except Exception as e:
        return JSONResponse({"error": f"解析失败: {str(e)}"}, status_code=400)

    task_id = str(uuid.uuid4())[:8]
    tasks[task_id] = {
        "songs": songs,
        "results": None,
        "status": "parsed",
        "progress": {"done": 0, "total": len(songs), "last_song": "", "last_found": False},
    }

    return {
        "task_id": task_id,
        "songs": [
            {"name": s.name, "artist": s.artist, "album": s.album, "duration": s.duration}
            for s in songs
        ],
    }


async def _run_search(task_id: str):
    task = tasks[task_id]
    songs = task["songs"]
    total = len(songs)
    progress = task["progress"]

    sem = asyncio.Semaphore(2)
    done_count = 0

    async def _search_one(idx, song):
        nonlocal done_count
        async with sem:
            try:
                matches = await search_top_matches(song, top_n=3)
                match = matches[0] if matches else None
            except Exception:
                matches = []
                match = None
            done_count += 1
            progress["done"] = done_count
            progress["last_song"] = song.name
            progress["last_found"] = match is not None
            return {"index": idx, "song": song, "match": match, "candidates": matches}

    tasks_list = [_search_one(i, s) for i, s in enumerate(songs)]
    all_results = await asyncio.gather(*tasks_list)
    all_results = sorted(all_results, key=lambda x: x["index"])

    task["results"] = []
    for r in all_results:
        s = r["song"]
        m = r.get("match")
        task["results"].append({
            "song": {"name": s.name, "artist": s.artist, "duration": s.duration},
            "match": m,
            "candidates": r.get("candidates", []),
        })
    task["status"] = "searched"


@app.post("/search/{task_id}")
async def start_search(task_id: str):
    task = tasks.get(task_id)
    if not task:
        return JSONResponse({"error": "任务不存在"}, status_code=404)

    task["status"] = "searching"
    task["progress"] = {"done": 0, "total": len(task["songs"]), "last_song": "", "last_found": False}
    asyncio.create_task(_run_search(task_id))
    return {"status": "searching"}


@app.get("/search/{task_id}/progress")
async def search_progress(task_id: str):
    task = tasks.get(task_id)
    if not task:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    return {
        "status": task["status"],
        "progress": task["progress"],
    }


@app.get("/search/{task_id}/results")
async def search_results(task_id: str):
    task = tasks.get(task_id)
    if not task:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    if task["status"] != "searched":
        return JSONResponse({"error": "搜索尚未完成"}, status_code=400)
    return {"results": task["results"]}


@app.post("/search/{task_id}/retry")
async def retry_search(task_id: str, request: Request):
    task = tasks.get(task_id)
    if not task:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    if task["status"] != "searched" or not task["results"]:
        return JSONResponse({"error": "搜索尚未完成"}, status_code=400)

    body = await request.json()
    idx = body.get("index")
    keyword = body.get("keyword", "").strip()
    if idx is None or not keyword:
        return JSONResponse({"error": "参数缺失"}, status_code=400)

    if idx < 0 or idx >= len(task["results"]):
        return JSONResponse({"error": "索引越界"}, status_code=400)

    song_data = task["results"][idx]["song"]
    song = Song(name=keyword, artist=song_data.get("artist", ""), duration=song_data.get("duration", 0))

    try:
        match = await search_best_match(song)
    except Exception:
        match = None

    task["results"][idx]["match"] = match
    return {"match": match}


@app.post("/search/{task_id}/switch")
async def switch_candidate(task_id: str, request: Request):
    task = tasks.get(task_id)
    if not task:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    if task["status"] != "searched" or not task["results"]:
        return JSONResponse({"error": "搜索尚未完成"}, status_code=400)

    body = await request.json()
    idx = body.get("index")
    candidate_idx = body.get("candidate_index", 0)
    if idx is None:
        return JSONResponse({"error": "参数缺失"}, status_code=400)

    if idx < 0 or idx >= len(task["results"]):
        return JSONResponse({"error": "索引越界"}, status_code=400)

    candidates = task["results"][idx].get("candidates", [])
    if candidate_idx < 0 or candidate_idx >= len(candidates):
        return JSONResponse({"error": "候选索引越界"}, status_code=400)

    task["results"][idx]["match"] = candidates[candidate_idx]
    return {"match": candidates[candidate_idx]}


@app.post("/verify_bvid")
async def verify_bvid(request: Request):
    from bilibili_api import video as bilibili_video

    body = await request.json()
    bvid = body.get("bvid", "").strip()
    if not bvid:
        return JSONResponse({"error": "请输入BV号"}, status_code=400)

    try:
        v = bilibili_video.Video(bvid=bvid)
        info = await v.get_info()
        return {
            "valid": True,
            "title": info.get("title", ""),
            "author": info.get("owner", {}).get("name", ""),
            "duration": info.get("duration", 0),
            "aid": info.get("aid", 0),
        }
    except Exception as e:
        return {"valid": False, "error": str(e)}


async def _run_collect(task_id: str, media_id: int, aids: list[int], credential):
    task = tasks[task_id]
    progress = task["collect_progress"]
    delay = 0.8
    results = []
    for i, aid in enumerate(aids):
        from bilibili.collector import add_video_to_favorite
        success = await add_video_to_favorite(media_id, aid, credential)
        results.append({"index": i, "aid": aid, "success": success})
        progress["done"] = i + 1
        progress["last_aid"] = aid
        progress["last_success"] = success
        if i < len(aids) - 1:
            await asyncio.sleep(delay)
    task["status"] = "done"
    task["collect_results"] = results


@app.post("/collect/{task_id}")
async def start_collect(task_id: str, request: Request):
    task = tasks.get(task_id)
    if not task:
        return JSONResponse({"error": "任务不存在"}, status_code=404)

    credential = load_credential()
    if not credential:
        return JSONResponse({"error": "请先登录B站"}, status_code=401)

    body = await request.json()
    fav_title = body.get("title", "歌单转存")
    selected = body.get("selected", [])

    valid_aids = []
    for item in selected:
        aid = item.get("aid")
        if aid and aid != 0:
            valid_aids.append(aid)

    if not valid_aids:
        return JSONResponse({"error": "没有有效的视频可以添加"}, status_code=400)

    try:
        media_id = await create_favorite(fav_title, credential)
    except Exception as e:
        return JSONResponse({"error": f"创建收藏夹失败: {str(e)}"}, status_code=500)

    task["status"] = "collecting"
    task["media_id"] = media_id
    task["collect_progress"] = {"done": 0, "total": len(valid_aids), "last_aid": 0, "last_success": False}
    asyncio.create_task(_run_collect(task_id, media_id, valid_aids, credential))
    return {"status": "collecting", "media_id": media_id, "total": len(valid_aids)}


@app.get("/collect/{task_id}/progress")
async def collect_progress(task_id: str):
    task = tasks.get(task_id)
    if not task:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    result = {
        "status": task["status"],
        "progress": task.get("collect_progress", {}),
    }
    if task["status"] == "done":
        results = task.get("collect_results", [])
        success_count = sum(1 for r in results if r["success"])
        result["summary"] = {
            "total": len(results),
            "success": success_count,
            "failed": len(results) - success_count,
        }
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
