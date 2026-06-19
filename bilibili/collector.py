import asyncio
from bilibili_api import favorite_list, video, Credential, user


async def create_favorite(title: str, credential: Credential, introduction: str = "") -> int:
    result = await favorite_list.create_video_favorite_list(
        title=title,
        introduction=introduction,
        credential=credential,
    )
    return result.get("id", 0)


async def add_video_to_favorite(
    media_id: int,
    aid: int,
    credential: Credential,
) -> bool:
    try:
        v = video.Video(aid=aid, credential=credential)
        await v.set_favorite(add_media_ids=[media_id])
        return True
    except Exception as e:
        print(f"添加视频 {aid} 到收藏夹失败: {e}")
        return False


async def batch_add_to_favorite(
    media_id: int,
    aids: list[int],
    credential: Credential,
    delay: float = 0.5,
) -> list[dict]:
    results = []
    for i, aid in enumerate(aids):
        success = await add_video_to_favorite(media_id, aid, credential)
        results.append({"index": i, "aid": aid, "success": success})
        if i < len(aids) - 1:
            await asyncio.sleep(delay)
    return results


async def get_user_info(credential: Credential) -> dict:
    return await user.get_self_info(credential=credential)
